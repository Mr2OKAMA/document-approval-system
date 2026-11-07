"""DBとPDFを日付付きzipにバックアップする。 使い方: python -m scripts.backup [出力先ディレクトリ]"""
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from app import db


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"docmgmt_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "app.db"
        src = sqlite3.connect(db.DATA_DIR / "app.db")
        dst = sqlite3.connect(snap)
        src.backup(dst)  # 稼働中でも整合性のあるスナップショットを取る
        dst.close()
        src.close()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "app.db")
            for f in (db.DATA_DIR / "files").glob("*"):
                z.write(f, f"files/{f.name}")
    print(f"バックアップを作成しました: {target}")


if __name__ == "__main__":
    main()
