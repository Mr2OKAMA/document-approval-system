"""最初の管理者アカウントを作成する。 使い方: python -m scripts.create_admin"""
import getpass
import sys

from app import db


def main() -> None:
    db.init_db()
    login_id = input("管理者ID: ").strip()
    name = input("氏名: ").strip()
    password = getpass.getpass("パスワード(8文字以上): ")
    if not login_id or not name or len(password) < 8:
        sys.exit("入力が正しくありません")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO users(login_id,name,role,password_hash,created_at) VALUES(?,?,?,?,?)",
            (login_id, name, "admin", db.hash_password(password), db.now()),
        )
        db.log(conn, "system", "アカウント作成", login_id, "role=admin")
    print("作成しました")


if __name__ == "__main__":
    main()
