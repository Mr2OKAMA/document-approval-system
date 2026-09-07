# document-approval-system

社内向けの書類申請・承認・管理WEBアプリです。Next.js ベースの UI / API から Notion データベースを操作し、申請フォーム・一覧表示・ステータス管理を行います。Microsoft Teams は Incoming Webhook 設定時に通知連携できます。

## 技術スタック

- Next.js（App Router）
- TypeScript
- Tailwind CSS
- Notion API（`@notionhq/client`）
- axios

> セキュリティ上の理由で、依存パッケージは既知脆弱性のある Next.js 14 系ではなく、安全な現行版を採用しています。実装構成自体は要件どおり Next.js App Router / TypeScript / API Routes ベースです。

## セットアップ

```bash
npm install
cp .env.example .env.local
npm run dev
```

`.env.local` には少なくとも以下を設定してください。

```env
NOTION_API_KEY=
NOTION_DATABASE_ID=
NOTION_PAGE_SIZE=50
MICROSOFT_TEAMS_WEBHOOK_URL=
NEXT_PUBLIC_APP_NAME=Document Approval System
```

Notion 未設定時でも、UI と API の確認ができるようにメモリ上のサンプルデータで動作します。

## 主な画面・API

- `/` : ダッシュボード
- `/applications` : 新規申請フォーム
- `/applications/list` : 申請一覧
- `/applications/[id]` : 申請詳細
- `GET/POST /api/applications` : 申請一覧取得 / 新規作成
- `GET/PATCH/DELETE /api/applications/[id]` : 詳細取得 / ステータス更新 / 削除
- `GET/POST /api/notion/sync` : Notion 同期状態確認

## 開発コマンド

```bash
npm run lint
npm run typecheck
npm run build
```

## Notion データベース設計

詳細は [`docs/NOTION_DB_DESIGN.md`](docs/NOTION_DB_DESIGN.md) を参照してください。
