from fastapi import APIRouter, Depends, Form, HTTPException, Request

from .. import db, services
from ..core import STAFF, back, check_csrf, get_conn, render, require

router = APIRouter()
MANAGE = ("admin", "author")


@router.get("/equipment")
def equipment(request: Request, user=Depends(require(*STAFF)), conn=Depends(get_conn)):
    rows = []
    for e in conn.execute("SELECT * FROM equipment ORDER BY active DESC, name"):
        due = services.parse_date(e["calibration_due"]) if e["calibration_due"] else None
        docs = conn.execute(
            "SELECT d.doc_no, d.title FROM doc_equipment x JOIN documents d ON d.id=x.document_id WHERE x.equipment_id=? ORDER BY d.doc_no",
            (e["id"],)).fetchall()
        cals = conn.execute(
            "SELECT c.*, u.name FROM calibrations c JOIN users u ON u.id=c.recorded_by WHERE equipment_id=? ORDER BY done_on DESC, c.id DESC LIMIT 5",
            (e["id"],)).fetchall()
        rows.append({"e": e, "due": due, "state": services.due_state(due) if e["active"] else "", "docs": docs, "cals": cals})
    return render(request, "equipment.html", user, rows=rows, can_manage=user["role"] in MANAGE)


@router.post("/equipment", dependencies=[Depends(check_csrf)])
def create(request: Request, name: str = Form(...), model: str = Form(""), serial_no: str = Form(""),
           in_use_since: str = Form(...), calibration_cycle_months: int = Form(12), note: str = Form(""),
           user=Depends(require(*MANAGE)), conn=Depends(get_conn)):
    if not name.strip() or not services.parse_date(in_use_since) or not 1 <= calibration_cycle_months <= 120:
        return back(request, "/equipment", "名称・使用開始日・校正周期を正しく入力してください")
    conn.execute(
        "INSERT INTO equipment(name,model,serial_no,in_use_since,calibration_cycle_months,note,created_at) VALUES(?,?,?,?,?,?,?)",
        (name.strip(), model.strip(), serial_no.strip(), in_use_since, calibration_cycle_months, note.strip(), db.now()))
    db.log(conn, user["login_id"], "設備登録", name.strip(), f"使用開始日={in_use_since}")
    return back(request, "/equipment", "設備を登録しました")


@router.post("/equipment/{eid}/calibration", dependencies=[Depends(check_csrf)])
def calibrate(eid: int, request: Request, done_on: str = Form(...), result: str = Form(...), note: str = Form(""),
              user=Depends(require(*MANAGE)), conn=Depends(get_conn)):
    e = conn.execute("SELECT * FROM equipment WHERE id=?", (eid,)).fetchone()
    if not e:
        raise HTTPException(404)
    d = services.parse_date(done_on)
    if not d or d > db.today() or result not in ("合格", "不合格"):
        return back(request, "/equipment", "実施日(未来日不可)と結果を正しく入力してください")
    due = services.add_months(d, e["calibration_cycle_months"]).isoformat()
    conn.execute("INSERT INTO calibrations(equipment_id,done_on,due_on,result,note,recorded_by,recorded_at) VALUES(?,?,?,?,?,?,?)",
                 (eid, done_on, due, result, note.strip(), user["id"], db.now()))
    # 期限は実施日が最新の記録から決める(過去日の追記で上書きしない)。不合格が最新なら期限なし
    latest = conn.execute("SELECT result, due_on FROM calibrations WHERE equipment_id=? ORDER BY done_on DESC, id DESC LIMIT 1",
                          (eid,)).fetchone()
    conn.execute("UPDATE equipment SET calibration_due=? WHERE id=?",
                 (latest["due_on"] if latest["result"] == "合格" else None, eid))
    db.log(conn, user["login_id"], "校正記録", e["name"], f"{done_on} {result}")
    return back(request, "/equipment", "校正を記録しました")


@router.post("/equipment/{eid}/toggle", dependencies=[Depends(check_csrf)])
def toggle(eid: int, request: Request, user=Depends(require(*MANAGE)), conn=Depends(get_conn)):
    e = conn.execute("SELECT * FROM equipment WHERE id=?", (eid,)).fetchone()
    if not e:
        raise HTTPException(404)
    new = 0 if e["active"] else 1
    conn.execute("UPDATE equipment SET active=? WHERE id=?", (new, eid))
    db.log(conn, user["login_id"], "設備使用再開" if new else "設備使用停止", e["name"])
    return back(request, "/equipment")
