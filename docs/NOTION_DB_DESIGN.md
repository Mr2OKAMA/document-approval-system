# Notion データベース設計

## 想定データベース名

`Applications`

## プロパティ定義

| プロパティ名 | 型 | 必須 | 用途 |
| --- | --- | --- | --- |
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

## ステータス遷移

- `未承認` → `承認中`
- `承認中` → `完了`
- `承認中` → `却下`

必要であれば Notion の Board View を `Status` 単位で作成し、申請進捗を可視化します。

## Teams 連携の考え方

- 新規申請作成時に Webhook で通知
- Power Automate から Notion の `Status` を更新することで承認フローと連携
- コメントや承認者名を更新すると、アプリの詳細画面にも反映
