import { Client } from "@notionhq/client";

const notion = new Client({
  auth: process.env.NOTION_API_KEY,
});

const DATABASE_ID = process.env.NOTION_DATABASE_ID || "";

/**
 * Notion データベース操作のデモスクリプト
 * - データベース情報の取得
 * - 既存プロパティの確認
 * - プロパティの表示
 * - サンプルデータの作成
 */

interface PropertyType {
  [key: string]: any;
}

/**
 * メイン処理
 */
async function main() {
  if (!DATABASE_ID || !process.env.NOTION_API_KEY) {
    console.error(
      "❌ NOTION_DATABASE_ID または NOTION_API_KEY が設定されていません"
    );
    console.error(
      "💡 .env.local ファイルを確認してください。\n例:\nNOTION_API_KEY=ntn_xxxxx\nNOTION_DATABASE_ID=xxxxx"
    );
    process.exit(1);
  }

  console.log("🚀 Notion データベース セットアップデモを開始します...\n");

  try {
    // ステップ 1: データベース情報を取得
    await step1_GetDatabaseInfo();

    // ステップ 2: 既存プロパティを表示
    await step2_DisplayProperties();

    // ステップ 3: 必要なプロパティをチェック・作成
    await step3_CheckAndCreateProperties();

    // ステップ 4: サンプルデータを作成
    await step4_CreateSampleData();

    console.log("\n✨ すべてのセットアップが完了しました！\n");
    console.log("📊 Notion データベースの状態:");
    console.log(`  Database ID: ${DATABASE_ID}`);
    console.log("  URL: https://www.notion.so/" + DATABASE_ID.replace(/-/g, ""));
    console.log(
      "\n💡 次のステップ:\n  1. npm run dev でアプリを起動\n  2. http://localhost:3000 にアクセス\n  3. 申請フォームをテスト"
    );
  } catch (error) {
    console.error("❌ エラーが発生しました:", error);
    process.exit(1);
  }
}

/**
 * ステップ 1: データベース情報を取得・表示
 */
async function step1_GetDatabaseInfo() {
  console.log("📋 [ステップ 1] Notion データベース情報を取得中...\n");

  try {
    const database = await notion.databases.retrieve({
      database_id: DATABASE_ID,
    });

    console.log("✅ データベース情報:");
    console.log(`  タイトル: ${database.title}`);
    console.log(`  作成日時: ${database.created_time}`);
    console.log(`  最終更新: ${database.last_edited_time}`);
    console.log("");
  } catch (error) {
    console.error("❌ データベース取得に失敗しました:", error);
    throw error;
  }
}

/**
 * ステップ 2: 既存プロパティを表示
 */
async function step2_DisplayProperties() {
  console.log("📊 [ステップ 2] 既存プロパティを確認中...\n");

  try {
    const database = await notion.databases.retrieve({
      database_id: DATABASE_ID,
    });

    const properties = database.properties;
    const propertyNames = Object.keys(properties);

    if (propertyNames.length === 0) {
      console.log("⚠️  プロパティがまだ設定されていません");
      console.log("💡 Notion UI からプロパティを手動で追加してください\n");
      return;
    }

    console.log(`✅ 既存プロパティ (${propertyNames.length}個):\n`);

    const propertyTable: string[] = [];
    propertyNames.forEach((name) => {
      const prop = properties[name];
      const type = prop.type;
      propertyTable.push(`  • ${name.padEnd(20)} : ${type}`);
    });

    propertyTable.forEach((line) => console.log(line));
    console.log("");
  } catch (error) {
    console.error("❌ プロパティ取得に失敗しました:", error);
    throw error;
  }
}

/**
 * ステップ 3: 必要なプロパティをチェック
 */
async function step3_CheckAndCreateProperties() {
  console.log(
    "🔧 [ステップ 3] 必要なプロパティをチェック中...\n"
  );

  try {
    const database = await notion.databases.retrieve({
      database_id: DATABASE_ID,
    });

    const properties = database.properties;

    // 必要なプロパティリスト
    const requiredProperties = [
      "Title",
      "ApplicantName",
      "ApplicantEmail",
      "DocumentType",
      "Description",
      "Status",
      "AppliedAt",
      "ApproverName",
      "Comment",
      "AttachmentInfo",
    ];

    console.log("必要なプロパティチェック:\n");

    const missingProperties: string[] = [];

    requiredProperties.forEach((propName) => {
      if (properties[propName]) {
        console.log(`  ✅ "${propName}" : 存在します`);
      } else {
        console.log(`  ❌ "${propName}" : 存在しません`);
        missingProperties.push(propName);
      }
    });

    if (missingProperties.length > 0) {
      console.log(
        `\n⚠️  ${missingProperties.length}個のプロパティが不足しています`
      );
      console.log("\n💡 以下の方法で追加してください:");
      console.log("  1. Notion UI を開く: https://www.notion.so/");
      console.log(
        `  2. データベース ID: ${DATABASE_ID}`
      );
      console.log("  3. 「Add a property」をクリック");
      console.log("  4. 以下のプロパティを追加:");

      missingProperties.forEach((prop) => {
        const propTypes: { [key: string]: string } = {
          Title: "Title",
          ApplicantName: "Rich text",
          ApplicantEmail: "Email",
          DocumentType: "Select (稟議書, 経費申請, 契約書, その他)",
          Description: "Rich text",
          Status: "Select (未承認, 承認中, 完了, 却下)",
          AppliedAt: "Date",
          ApproverName: "Rich text",
          Comment: "Rich text",
          AttachmentInfo: "Rich text",
        };
        console.log(`     - ${prop} (${propTypes[prop]})`);
      });
      console.log("");
    } else {
      console.log("\n✅ すべての必要なプロパティが揃っています！\n");
    }
  } catch (error) {
    console.error("❌ プロパティチェックに失敗しました:", error);
    throw error;
  }
}

/**
 * ステップ 4: サンプルデータを作成
 */
async function step4_CreateSampleData() {
  console.log(
    "📝 [ステップ 4] サンプルデータを作成中...\n"
  );

  try {
    const database = await notion.databases.retrieve({
      database_id: DATABASE_ID,
    });

    const properties = database.properties;

    // Title プロパティが存在するかチェック
    if (!properties["Title"]) {
      console.log("⚠️  Title プロパティが不足しているため、サンプルデータの作成をスキップします");
      console.log("💡 まず Notion UI からプロパティを追加してください\n");
      return;
    }

    // サンプルデータ
    const sampleDataList = [
      {
        title: "テスト申請 - 経費申請（交通費）",
        applicantName: "田中太郎",
        applicantEmail: "tanaka@example.com",
        documentType: "経費申請",
        description: "出張時のタクシー代を申請します。",
        status: "未承認",
      },
      {
        title: "テスト申請 - 稟議書（新規プロジェクト）",
        applicantName: "鈴木花子",
        applicantEmail: "suzuki@example.com",
        documentType: "稟議書",
        description: "新規プロジェクトの予算承認を申請します。",
        status: "未承認",
      },
      {
        title: "テスト申請 - 契約書（ベンダー契約）",
        applicantName: "佐藤次郎",
        applicantEmail: "sato@example.com",
        documentType: "契約書",
        description: "外部ベンダーとの契約書です。",
        status: "承認中",
      },
    ];

    let successCount = 0;
    let skipCount = 0;

    for (const sampleData of sampleDataList) {
      try {
        const pageData: PropertyType = {
          Title: {
            title: [
              {
                text: {
                  content: sampleData.title,
                },
              },
            ],
          },
        };

        // オプショナルなプロパティを追加
        if (properties["ApplicantName"]) {
          pageData.ApplicantName = {
            rich_text: [
              {
                text: {
                  content: sampleData.applicantName,
                },
              },
            ],
          };
        }

        if (properties["ApplicantEmail"]) {
          pageData.ApplicantEmail = {
            email: sampleData.applicantEmail,
          };
        }

        if (properties["DocumentType"]) {
          pageData.DocumentType = {
            select: {
              name: sampleData.documentType,
            },
          };
        }

        if (properties["Description"]) {
          pageData.Description = {
            rich_text: [
              {
                text: {
                  content: sampleData.description,
                },
              },
            ],
          };
        }

        if (properties["Status"]) {
          pageData.Status = {
            select: {
              name: sampleData.status,
            },
          };
        }

        if (properties["AppliedAt"]) {
          pageData.AppliedAt = {
            date: {
              start: new Date().toISOString().split("T")[0],
            },
          };
        }

        const response = await notion.pages.create({
          parent: {
            database_id: DATABASE_ID,
          },
          properties: pageData,
        });

        console.log(`  ✅ "${sampleData.title}" を作成しました`);
        successCount++;
      } catch (error) {
        console.log(
          `  ⚠️  "${sampleData.title}" の作成をスキップしました（プロパティ不足）`
        );
        skipCount++;
      }
    }

    console.log(`\n📊 結果: ${successCount}個作成, ${skipCount}個スキップ\n`);
  } catch (error) {
    console.error("❌ サンプルデータ作成に失敗しました:", error);
    throw error;
  }
}

// メイン処理実行
main();
