/// <reference types="node" />

import { Client, isFullDataSource, isFullPageOrDataSource } from '@notionhq/client';
import type {
  DataSourceObjectResponse,
  UpdateDataSourceParameters,
} from '@notionhq/client/build/src/api-endpoints';

type DataSourcePropertiesUpdate = NonNullable<UpdateDataSourceParameters['properties']>;
type PageProperties = NonNullable<Parameters<Client['pages']['create']>[0]['properties']>;
type SelectColor = 'blue' | 'green' | 'orange' | 'gray' | 'red' | 'yellow';

interface DemoApplication {
  title: string;
  applicantName: string;
  applicantEmail: string;
  documentType: '稟議書' | '経費申請' | '契約書' | 'その他';
  description: string;
  status: '未承認' | '承認中' | '完了' | '却下';
  appliedAt: string;
  approverName?: string;
  comment?: string;
  attachmentInfo?: string;
}

interface SelectOptionDefinition {
  name: string;
  color: SelectColor;
}

const DATABASE_ID = process.env.NOTION_DATABASE_ID ?? '';
const NOTION_API_KEY = process.env.NOTION_API_KEY ?? '';

const notion = new Client({
  auth: NOTION_API_KEY,
});

const REQUIRED_PROPERTY_DEFINITIONS = {
  Title: {
    type: 'title',
    title: {},
  },
  ApplicantName: {
    type: 'rich_text',
    rich_text: {},
  },
  ApplicantEmail: {
    type: 'email',
    email: {},
  },
  DocumentType: {
    type: 'select',
    select: {
      options: [
        { name: '稟議書', color: 'blue' },
        { name: '経費申請', color: 'green' },
        { name: '契約書', color: 'orange' },
        { name: 'その他', color: 'gray' },
      ],
    },
  },
  Description: {
    type: 'rich_text',
    rich_text: {},
  },
  Status: {
    type: 'select',
    select: {
      options: [
        { name: '未承認', color: 'red' },
        { name: '承認中', color: 'yellow' },
        { name: '完了', color: 'green' },
        { name: '却下', color: 'gray' },
      ],
    },
  },
  AppliedAt: {
    type: 'date',
    date: {},
  },
  ApproverName: {
    type: 'rich_text',
    rich_text: {},
  },
  Comment: {
    type: 'rich_text',
    rich_text: {},
  },
  AttachmentInfo: {
    type: 'rich_text',
    rich_text: {},
  },
} satisfies DataSourcePropertiesUpdate;

const SELECT_OPTION_DEFINITIONS: Record<'DocumentType' | 'Status', SelectOptionDefinition[]> = {
  DocumentType: [
    { name: '稟議書', color: 'blue' },
    { name: '経費申請', color: 'green' },
    { name: '契約書', color: 'orange' },
    { name: 'その他', color: 'gray' },
  ],
  Status: [
    { name: '未承認', color: 'red' },
    { name: '承認中', color: 'yellow' },
    { name: '完了', color: 'green' },
    { name: '却下', color: 'gray' },
  ],
};

const DEMO_APPLICATIONS: DemoApplication[] = [
  {
    title: '新規プロジェクト開発予算承認',
    applicantName: '山田太郎',
    applicantEmail: 'yamada@example.com',
    documentType: '稟議書',
    description: '新規プロジェクト開発の予算承認を申請します。',
    status: '未承認',
    appliedAt: '2026-09-07',
  },
  {
    title: '出張時のタクシー代',
    applicantName: '鈴木花子',
    applicantEmail: 'suzuki@example.com',
    documentType: '経費申請',
    description: '東京への出張時にタクシーを利用しました。',
    status: '承認中',
    appliedAt: '2026-09-06',
    approverName: '田中部長',
    comment: '確認中です',
  },
  {
    title: '社内会議費',
    applicantName: '佐藤次郎',
    applicantEmail: 'sato@example.com',
    documentType: '経費申請',
    description: '社内会議で使用したカフェの費用です。',
    status: '承認中',
    appliedAt: '2026-09-05',
  },
  {
    title: 'ベンダー企業との契約',
    applicantName: '伊藤由美',
    applicantEmail: 'ito@example.com',
    documentType: '契約書',
    description: '外部ベンダーとの開発委託契約書です。',
    status: '完了',
    appliedAt: '2026-09-01',
    approverName: '高橋副部長',
    comment: '契約書を確認し、承認いたしました。',
  },
  {
    title: 'テスト申請',
    applicantName: '新入太郎',
    applicantEmail: 'shinin@example.com',
    documentType: 'その他',
    description: 'システムテスト用のデモ申請です。',
    status: '却下',
    appliedAt: '2026-09-03',
    approverName: '管理者',
    comment: '本番環境では使用しないため却下いたします。',
  },
];

function assertEnvironmentVariables() {
  if (NOTION_API_KEY && DATABASE_ID) {
    return;
  }

  const missing: string[] = [];
  if (!NOTION_API_KEY) {
    missing.push('NOTION_API_KEY');
  }
  if (!DATABASE_ID) {
    missing.push('NOTION_DATABASE_ID');
  }

  throw new Error(`環境変数が不足しています: ${missing.join(', ')}`);
}

function getPlainTextFromRichText(items: unknown): string {
  if (!Array.isArray(items)) {
    return '';
  }

  return items
    .map((item) =>
      item && typeof item === 'object' && 'plain_text' in item && typeof item.plain_text === 'string'
        ? item.plain_text
        : '',
    )
    .join('');
}

async function getDataSource(): Promise<DataSourceObjectResponse> {
  const response = await notion.dataSources.retrieve({
    data_source_id: DATABASE_ID,
  });

  if (!isFullDataSource(response)) {
    throw new Error('Notion データソースの詳細を取得できませんでした。');
  }

  return response;
}

async function updateDataSourceProperties(properties: DataSourcePropertiesUpdate) {
  if (Object.keys(properties).length === 0) {
    return;
  }

  await notion.dataSources.update({
    data_source_id: DATABASE_ID,
    properties,
  });
}

async function setupProperties() {
  console.log('✅ [ステップ 1] プロパティをセットアップ中...');

  const dataSource = await getDataSource();
  const propertiesToCreate: DataSourcePropertiesUpdate = {};

  for (const [propertyName, propertyDefinition] of Object.entries(
    REQUIRED_PROPERTY_DEFINITIONS,
  )) {
    const existingProperty = dataSource.properties[propertyName];

    if (!existingProperty) {
      propertiesToCreate[propertyName] = propertyDefinition;
      console.log(`  ✓ ${propertyName} プロパティ：作成予定`);
      continue;
    }

    if (existingProperty.type !== propertyDefinition.type) {
      console.log(
        `  ⚠️ ${propertyName} プロパティ：既存タイプが ${existingProperty.type} のためスキップ`,
      );
      continue;
    }

    console.log(`  ✓ ${propertyName} プロパティ：既に存在`);
  }

  await updateDataSourceProperties(propertiesToCreate);
}

function buildMergedSelectOptions(
  existingOptions: Array<{ id: string; name: string; color: string }>,
  expectedOptions: SelectOptionDefinition[],
) {
  const mergedOptions: Array<{ id?: string; name: string; color: SelectColor }> = existingOptions.map(
    (option) => ({
    id: option.id,
    name: option.name,
    color: option.color as SelectColor,
    }),
  );

  const existingOptionNames = new Set(existingOptions.map((option) => option.name));

  for (const option of expectedOptions) {
    if (!existingOptionNames.has(option.name)) {
      mergedOptions.push(option);
    }
  }

  return mergedOptions;
}

async function setupSelectOptions() {
  console.log('\n✅ [ステップ 2] Select オプションを設定中...');

  const dataSource = await getDataSource();
  const propertiesToUpdate: DataSourcePropertiesUpdate = {};

  for (const [propertyName, options] of Object.entries(SELECT_OPTION_DEFINITIONS) as Array<
    [keyof typeof SELECT_OPTION_DEFINITIONS, SelectOptionDefinition[]]
  >) {
    const property = dataSource.properties[propertyName];

    if (!property) {
      console.log(`  ⚠️ ${propertyName} オプション設定：プロパティが存在しないためスキップ`);
      continue;
    }

    if (property.type !== 'select') {
      console.log(
        `  ⚠️ ${propertyName} オプション設定：select 型ではないためスキップ`,
      );
      continue;
    }

    const mergedOptions = buildMergedSelectOptions(property.select.options, options);

    propertiesToUpdate[propertyName] = {
      type: 'select',
      select: {
        options: mergedOptions,
      },
    };

    console.log(`  ✓ ${propertyName} オプション設定：完了`);
  }

  await updateDataSourceProperties(propertiesToUpdate);
}

function toRichText(content?: string) {
  return content ? [{ text: { content } }] : [];
}

function buildDemoPageProperties(application: DemoApplication): PageProperties {
  return {
    Title: {
      title: [{ text: { content: application.title } }],
    },
    ApplicantName: {
      rich_text: toRichText(application.applicantName),
    },
    ApplicantEmail: {
      email: application.applicantEmail,
    },
    DocumentType: {
      select: {
        name: application.documentType,
      },
    },
    Description: {
      rich_text: toRichText(application.description),
    },
    Status: {
      select: {
        name: application.status,
      },
    },
    AppliedAt: {
      date: {
        start: application.appliedAt,
      },
    },
    ApproverName: {
      rich_text: toRichText(application.approverName),
    },
    Comment: {
      rich_text: toRichText(application.comment),
    },
    AttachmentInfo: {
      rich_text: toRichText(application.attachmentInfo),
    },
  };
}

async function getExistingDemoTitles() {
  const response = await notion.dataSources.query({
    data_source_id: DATABASE_ID,
    page_size: 100,
  });

  const titles = new Set<string>();

  for (const result of response.results) {
    if (!isFullPageOrDataSource(result) || !('properties' in result)) {
      continue;
    }

    const titleProperty = result.properties.Title;
    if (
      titleProperty &&
      typeof titleProperty === 'object' &&
      'type' in titleProperty &&
      titleProperty.type === 'title'
    ) {
      titles.add(getPlainTextFromRichText(titleProperty.title));
    }
  }

  return titles;
}

async function insertDemoData() {
  console.log('\n✅ [ステップ 3] デモデータを挿入中...');

  const existingTitles = await getExistingDemoTitles();
  let createdCount = 0;

  for (const application of DEMO_APPLICATIONS) {
    if (existingTitles.has(application.title)) {
      console.log(`  ✓ "${application.title}" は既に存在するためスキップしました`);
      continue;
    }

    await notion.pages.create({
      parent: {
        data_source_id: DATABASE_ID,
      },
      properties: buildDemoPageProperties(application),
    });

    existingTitles.add(application.title);
    createdCount += 1;
    console.log(`  ✓ "${application.title}" を作成しました`);
  }

  return createdCount;
}

async function displaySummary(createdCount: number) {
  const dataSource = await getDataSource();
  const requiredPropertyCount = Object.keys(REQUIRED_PROPERTY_DEFINITIONS).filter(
    (name) => Boolean(dataSource.properties[name]),
  ).length;
  const notionUrl =
    dataSource.url || `https://www.notion.so/${DATABASE_ID.replace(/-/g, '')}`;

  console.log('\n✨ セットアップが完了しました！\n');
  console.log('📊 Notion データベースの状態:');
  console.log(`  Database ID: ${DATABASE_ID}`);
  console.log(`  URL: ${notionUrl}`);
  console.log(`  プロパティ数: ${requiredPropertyCount}個`);
  console.log(`  デモデータ数: ${DEMO_APPLICATIONS.length}件`);
  console.log(
    createdCount === 0
      ? '\n💡 デモデータはすべて既に存在していたため、新規作成はありませんでした。'
      : '\n💡 指定されたデモデータの投入が完了しました。'
  );
  console.log(
    '\n💡 次のステップ:\n  1. npm run dev でアプリを起動\n  2. http://localhost:3000 にアクセス\n  3. Notion データベースにデモデータが表示されることを確認',
  );
}

async function main() {
  console.log('🚀 Notion データベース 完全セットアップを開始します...\n');

  try {
    assertEnvironmentVariables();
    await setupProperties();
    await setupSelectOptions();
    const createdCount = await insertDemoData();
    await displaySummary(createdCount);
  } catch (error) {
    console.error('\n❌ セットアップ中にエラーが発生しました。');
    if (error instanceof Error) {
      console.error(`   ${error.message}`);
    } else {
      console.error(error);
    }
    process.exit(1);
  }
}

void main();
