from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request

from .. import db
from ..core import MIN_PASSWORD, back, check_csrf, current_user, get_conn, render

router = APIRouter()
MAX_FAILS = 5
LOCK_MINUTES = 15


@router.get("/login")
def login_form(request: Request):
    return render(request, "login.html")


@router.post("/login", dependencies=[Depends(check_csrf)])
def login(request: Request, login_id: str = Form(...), password: str = Form(...), conn=Depends(get_conn)):
    user = conn.execute("SELECT * FROM users WHERE login_id=? AND active=1", (login_id,)).fetchone()
    if user and user["locked_until"] and user["locked_until"] > db.now():
        db.log(conn, login_id, "ログイン拒否(ロック中)", "-")
        return back(request, "/login", f"アカウントがロックされています。{LOCK_MINUTES}分後に再試行するか、管理者に連絡してください")
    if not user or not db.verify_password(password, user["password_hash"]):
        if user:
            fails = user["failed_count"] + 1
            locked = None
            if fails >= MAX_FAILS:
                locked = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds")
                fails = 0
            conn.execute("UPDATE users SET failed_count=?, locked_until=? WHERE id=?", (fails, locked, user["id"]))
        db.log(conn, login_id, "ログイン失敗", "-")
        return back(request, "/login", "IDまたはパスワードが違います")
    conn.execute("UPDATE users SET failed_count=0, locked_until=NULL WHERE id=?", (user["id"],))
    request.session.clear()
    request.session["uid"] = user["id"]
    db.log(conn, login_id, "ログイン", "-")
    return back(request, "/")


@router.post("/logout", dependencies=[Depends(check_csrf)])
def logout(request: Request):
    request.session.clear()
    return back(request, "/login")


@router.get("/password")
def password_form(request: Request, user=Depends(current_user)):
    return render(request, "password.html", user)


@router.post("/password", dependencies=[Depends(check_csrf)])
def password_change(
    request: Request,
    current: str = Form(...),
    new: str = Form(...),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    if not db.verify_password(current, user["password_hash"]):
        return back(request, "/password", "現在のパスワードが違います")
    if len(new) < MIN_PASSWORD or new == user["login_id"] or new == current:
        return back(request, "/password", f"パスワードは{MIN_PASSWORD}文字以上で、IDや現在のパスワードと異なるものにしてください")
    conn.execute("UPDATE users SET password_hash=?, must_change_pw=0 WHERE id=?", (db.hash_password(new), user["id"]))
    db.log(conn, user["login_id"], "パスワード変更", user["login_id"])
    return back(request, "/", "パスワードを変更しました")
