# document-approval-system

社内向けの書類申請・承認・管理WEBアプリです。Next.js ベースの UI / API から Notion データベースを操作し、申請フォーム・一覧表示・ステータス管理を一元化します。

## 📊 Notion データベース

以下のリンクから Notion データベースにアクセスできます：

🔗 **[Notion データベースを開く](https://www.notion.so/3d458091301a804fb7d3efa3a3ba09b9)**

> **注意**: Notion ワークスペースへのアクセス権限が必要です。権限がない場合は管理者に申し込んでください。
>
> 運用上は `.env.local` の `NOTION_DATABASE_ID` を正本として管理し、必要に応じて `https://www.notion.so/<NOTION_DATABASE_IDからハイフンを除去した値>` を参照してください。

詳細な設計情報は [`docs/NOTION_DB_DESIGN.md`](docs/NOTION_DB_DESIGN.md) を参照してください。

## 技術スタック

- Next.js（App Router）
- TypeScript
- Tailwind CSS
- Notion API（`@notionhq/client`）
- axios

> セキュリティ上の理由で、依存パッケージは既知脆弱性のある Next.js 14 系ではなく、安全な現行版を採用しています。実装構成自体は要件どおり設計されています。

## セットアップ（ローカル開発）

### 1. 依存パッケージのインストール

```bash
npm install
```

### 2. 環境変数の設定

```bash
cp .env.example .env.local
```

`.env.local` に以下の値を設定してください（Vercel 本番環境でも同名の環境変数を設定します）：

```env
NOTION_API_KEY=ntn_xxxxxxxxxxxxx  # Notion API Key
NOTION_DATABASE_ID=xxxxxxxxxxxxxxx  # Notion Database ID
NOTION_PAGE_SIZE=50
MICROSOFT_TEAMS_WEBHOOK_URL=https://outlook.webhook.office.com/xxxxx
NEXT_PUBLIC_APP_NAME=Document Approval System
```

### 3. Notion データベースのセットアップ

以下のコマンドで、Notion データベースの初期設定を行います：

```bash
npm run setup:notion
```

このコマンドは以下を実行します：
- Notion データベースの接続確認
- 必要なプロパティの確認・作成
- サンプルデータの挿入

### 4. 開発サーバーの起動

```bash
npm run dev
```

`http://localhost:3000` でアプリケーションにアクセスできます（ローカル開発専用）。

ブラウザで開く（HTML画面）:
- [ダッシュボード](http://localhost:3000/)
- [新規申請フォーム](http://localhost:3000/applications)
- [申請一覧](http://localhost:3000/applications/list)

> Notion 未設定時でも、UI と API の確認ができるようにメモリ上のサンプルデータで動作します。

## 🌐 本番サイト（API利用可）

本番利用時は、Vercel にデプロイした URL を使用してください。

- **Production URL（例）**: `https://<your-vercel-project>.vercel.app`

### UI ルート
- `/` : ダッシュボード
- `/applications` : 新規申請フォーム
- `/applications/list` : 申請一覧
- `/applications/[id]` : 申請詳細

### API エンドポイント
- `GET/POST /api/applications` : 申請一覧取得 / 新規作成
- `GET/PATCH/DELETE /api/applications/[id]` : 詳細取得 / ステータス更新 / 削除
- `GET/POST /api/notion/sync` : Notion 同期状態確認

> GitHub Pages（`https://mr2okama.github.io/document-approval-system/`）は静的ホスティングのため、`/api/*` ルートは実行できません。API を利用する場合は Vercel の本番 URL を使用してください。

## 🚀 Vercel デプロイ手順（推奨）

1. Vercel ダッシュボードで `Mr2OKAMA/document-approval-system` リポジトリを Import
2. Framework Preset は Next.js（自動検出のデフォルト設定）を使用
3. Environment Variables を設定
   - `NOTION_API_KEY`
   - `NOTION_DATABASE_ID`
   - `NOTION_PAGE_SIZE`（任意）
   - `MICROSOFT_TEAMS_WEBHOOK_URL`（任意）
   - `NEXT_PUBLIC_APP_NAME`（任意）
4. Deploy を実行
5. 発行された本番 URL で UI と API を確認
   - UI: `/`, `/applications`, `/applications/list`, `/applications/[id]`
   - API: `GET/POST /api/applications`, `GET/PATCH/DELETE /api/applications/[id]`, `GET/POST /api/notion/sync`

### Vercel CLI（任意）

```bash
npm i -g vercel
vercel login
vercel
vercel --prod
```

## 開発コマンド

```bash
# Linting
npm run lint

# 型チェック
npm run typecheck

# ビルド
npm run build

# 本番環境で起動
npm start

# Notion データベース初期化
npm run setup:notion
```

## Notion データベース設計

詳細は [`docs/NOTION_DB_DESIGN.md`](docs/NOTION_DB_DESIGN.md) を参照してください。

### プロパティ一覧

| プロパティ名 | 型 | 必須 | 用途 |
|---|---|---|---|
| `Title` | Title | ○ | 申請件名 |
| `ApplicantName` | Rich text | ○ | 申請者名 |
| `ApplicantEmail` | Email | ○ | 申請者メールアドレス |
| `DocumentType` | Select | ○ | `稟議書` / `経費申請` / `契約書` / `その他` |
| `Description` | Rich text | ○ | 申請内容 |
| `Status` | Select | ○ | `未承認` / `承認中` / `完了` / `却下` |
| `AppliedAt` | Date | ○ | 申請日時 |
| `ApproverName` | Rich text | - | 承認者名 |
| `Comment` | Rich text | - | 承認コメント |
| `AttachmentInfo` | Rich text | - | 添付ファイル名や共有リンク |

### ステータス遷移フロー

```
未承認 → 承認中 → 完了
              ↓
             却下
```

## Microsoft Teams 連携

新規申請作成時に、自動的に Microsoft Teams に通知が送信されます。

### 設定手順

1. Microsoft Teams で Webhook を作成
2. `MICROSOFT_TEAMS_WEBHOOK_URL` を設定（ローカル開発は `.env.local`、本番は Vercel の Environment Variables）
3. Power Automate でフロー設定（別途ドキュメント参照）

## トラブルシューティング

### Notion API の接続エラー

```
❌ NOTION_API_KEY または NOTION_DATABASE_ID が設定されていません
```

**解決方法**: ローカル開発は `.env.local`、本番環境は Vercel の Environment Variables に正しい値が設定されているか確認してください。

### セットアップスクリプトの実行エラー

```bash
npm run setup:notion
```

エラーが発生した場合は、以下を確認してください：
- Notion API Key が有効か
- Database ID が正しいか
- Notion ワークスペースでこのアプリケーションに適切なアクセス権限があるか

## ライセンス

ISC

## 開発チーム

このプロジェクトは社内向け書類申請システムとして開発されています。
質問や機能リクエストは、[Issues](https://github.com/Mr2OKAMA/document-approval-system/issues) にお願いします。
