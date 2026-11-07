"""操作ログの連鎖とPDFのハッシュを検証する。 使い方: python -m scripts.verify"""
import sys

from app import db, services


def main() -> None:
    conn = db.connect()
    ng = 0
    if not db.verify_audit_chain(conn):
        print("NG: 操作ログの連鎖が一致しません")
        ng += 1
    for r in conn.execute("SELECT r.*, d.doc_no FROM revisions r JOIN documents d ON d.id=r.document_id"):
        if not services.file_ok(r):
            print(f"NG: {r['doc_no']} Rev.{r['rev_no']} のPDFが無い、またはハッシュ不一致")
            ng += 1
    print("検証OK" if not ng else f"{ng}件の問題があります")
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
