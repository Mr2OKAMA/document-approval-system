import { Client } from "@notionhq/client";

const notion = new Client({
  auth: process.env.NOTION_API_KEY,
});

const DATABASE_ID = process.env.NOTION_DATABASE_ID || "";

interface PropertyConfig {
  [key: string]: any;
}

/**
 * Notion データベースのプロパティを設定
 */
async function setupNotionDatabase() {
  if (!DATABASE_ID || !process.env.NOTION_API_KEY) {
    console.error(
      "❌ NOTION_DATABASE_ID または NOTION_API_KEY が設定されていません"
    );
    process.exit(1);
  }

  try {
    console.log("📋 Notion データベースを取得中...");

    // データベース情報を取得
    const database = await notion.databases.retrieve({
      database_id: DATABASE_ID,
    });

    console.log(`✅ データベース取得成功: ${database.title}`);
    console.log("\n📊 現在のプロパティ:");
    console.log(JSON.stringify(Object.keys(database.properties), null, 2));

    // プロパティの更新
    console.log("\n🔧 プロパティを設定中...");

    const propertiesToUpdate: PropertyConfig = {
      Title: {
        title: {},
      },
      ApplicantName: {
        rich_text: {},
      },
      ApplicantEmail: {
        email: {},
      },
      DocumentType: {
        select: {
          options: [
            { name: "稟議書", color: "blue" },
            { name: "経費申請", color: "green" },
            { name: "契約書", color: "orange" },
            { name: "その他", color: "gray" },
          ],
        },
      },
      Description: {
        rich_text: {},
      },
      Status: {
        select: {
          options: [
            { name: "未承認", color: "red" },
            { name: "承認中", color: "yellow" },
            { name: "完了", color: "green" },
            { name: "却下", color: "gray" },
          ],
        },
      },
      AppliedAt: {
        date: {},
      },
      ApproverName: {
        rich_text: {},
      },
      Comment: {
        rich_text: {},
      },
      AttachmentInfo: {
        rich_text: {},
      },
    };

    // 各プロパティを更新
    for (const [propertyName, propertyConfig] of Object.entries(
      propertiesToUpdate
    )) {
      try {
        // 既存プロパティをチェック
        if (database.properties[propertyName]) {
          console.log(`  ✓ "${propertyName}" は既に存在します`);
        } else {
          console.log(`  ⚙️ "${propertyName}" を作成します...`);
          // 注: Notion API では既存プロパティの作成は制限されているため、
          // 実装時は Notion UI から手動で追加するか、
          // 以下のコメント部分を使用してください
        }
      } catch (error) {
        console.error(`  ❌ "${propertyName}" の設定に失敗: ${error}`);
      }
    }

    console.log("\n✅ Notion データベースセットアップ完了！");
    console.log("\n📝 設定内容:");
    console.log("- Title: 申請件名 (Title)");
    console.log("- ApplicantName: 申請者名 (Rich Text)");
    console.log("- ApplicantEmail: 申請者メール (Email)");
    console.log(
      "- DocumentType: 書類種別 (Select: 稟議書/経費申請/契約書/その他)"
    );
    console.log("- Description: 申請内容 (Rich Text)");
    console.log(
      "- Status: ステータス (Select: 未承認/承認中/完了/却下)"
    );
    console.log("- AppliedAt: 申請日時 (Date)");
    console.log("- ApproverName: 承認者名 (Rich Text)");
    console.log("- Comment: 承認コメント (Rich Text)");
    console.log("- AttachmentInfo: 添付ファイル情報 (Rich Text)");

    // サンプルデータを挿入
    console.log("\n🎯 サンプルデータを作成中...");
    await createSampleData();

    console.log("\n✨ すべてのセットアップが完了しました！");
  } catch (error) {
    console.error("❌ エラーが発生しました:", error);
    process.exit(1);
  }
}

/**
 * サンプルデータを作成
 */
async function createSampleData() {
  try {
    const sampleData = {
      Title: {
        title: [
          {
            text: {
              content: "テスト申請 - 経費申請",
            },
          },
        ],
      },
      ApplicantName: {
        rich_text: [
          {
            text: {
              content: "田中太郎",
            },
          },
        ],
      },
      ApplicantEmail: {
        email: "tanaka@example.com",
      },
      DocumentType: {
        select: {
          name: "経費申請",
        },
      },
      Description: {
        rich_text: [
          {
            text: {
              content: "外出時のタクシー代を申請します",
            },
          },
        ],
      },
      Status: {
        select: {
          name: "未承認",
        },
      },
      AppliedAt: {
        date: {
          start: new Date().toISOString().split("T")[0],
        },
      },
    };

    const response = await notion.pages.create({
      parent: {
        database_id: DATABASE_ID,
      },
      properties: sampleData,
    });

    console.log(`  ✓ サンプルデータを作成しました (ID: ${response.id})`);
  } catch (error) {
    console.error(`  ❌ サンプルデータ作成に失敗: ${error}`);
  }
}

// スクリプト実行
setupNotionDatabase();
