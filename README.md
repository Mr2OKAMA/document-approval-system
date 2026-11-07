# 文書管理システム(プロトタイプ)

文書の**申請・承認**と**アカウント管理**を行う社内向けWebアプリ。設計は `docs/設計書.md` を参照。

## 起動
```
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
export DOCMGMT_SECRET="ランダムな長い文字列"      # 必須(セッション署名用)
export DOCMGMT_DATA=/path/to/data                # 社内の保存先(GitHub管理外)
.venv/bin/python -m scripts.create_admin         # 最初の管理者を作成
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```
HTTPSで運用する場合は `DOCMGMT_HTTPS=1` を設定する。

## 使い方
1. 管理者が「アカウント」画面で、申請者・承認者・閲覧者のアカウントを作成する。
2. 申請者が「新規申請」でPDF・改訂内容・改訂理由・適用開始日を登録する(既存の文書番号なら次の版になる)。
3. 承認者が「承認待ち」で内容を確認し、承認または差戻し(コメント必須)をする。
4. 承認済みの最新版が「文書一覧」に表示される。閲覧者には承認済みのみ見える。

## 主なルール
- 自分の申請は承認できない。管理者も承認はできない(承認者役割のみ)。
- 承認・差戻し後の版は変更・削除できない(DBトリガーで強制)。
- 操作ログは追記のみで、ハッシュ連鎖により改ざんを検知する(操作ログ画面で検証)。
- PDFはSHA-256を記録し、閲覧時に照合する。

## テスト
```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## 注意
- `data/`、`*.db`、`.env` はGitHubにコミットしない(`.gitignore`済み)。社外秘ファイルはGitHubに置かない。
- 本番運用前に、バックアップ(`DOCMGMT_DATA`全体)と復元手順を決めること。
- 未実装:周知・教育記録、見直し期限、承認の複数段階(確認→承認)、パスワードの試行回数制限。
