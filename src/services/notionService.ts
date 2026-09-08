import { Client } from '@notionhq/client';
import type { PageObjectResponse } from '@notionhq/client/build/src/api-endpoints';
import { isNotionConfigured, notionConfig, notionPropertyNames } from '@/config/notion';
import {
  APPLICATION_STATUSES,
  type Application,
  type ApplicationCreateInput,
  type ApplicationStatus,
  type ApplicationStatusUpdateInput,
} from '@/types/application';
import type { NotionSyncSummary } from '@/types/notion';
import { notifyApplicationCreated, notifyApplicationStatusChanged } from '@/services/teamsService';
import { canTransitionStatus } from '@/utils/validators';

const notion = isNotionConfigured ? new Client({ auth: notionConfig.apiKey }) : null;
const fallbackStore = new Map<string, Application>();

seedFallbackStore();

function seedFallbackStore() {
  if (fallbackStore.size > 0) {
    return;
  }

  const timestamp = new Date().toISOString();
  const sample: Application = {
    id: 'sample-application-1',
    title: '社内規程改定申請',
    applicantName: '山田 太郎',
    applicantEmail: 'taro.yamada@example.com',
    documentType: '稟議書',
    description: '社内規程の更新に伴う承認を依頼します。',
    attachmentInfo: 'shared-drive/regulation-update.pdf',
    status: '未承認',
    appliedAt: timestamp,
    approverName: '',
    comment: '',
    updatedAt: timestamp,
  };

  fallbackStore.set(sample.id, sample);
}

async function withRetry<T>(operation: () => Promise<T>, retries = 3, delayMs = 300): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (attempt < retries - 1) {
        await new Promise((resolve) => setTimeout(resolve, delayMs * (attempt + 1)));
      }
    }
  }

  throw lastError;
}

function getTextContent(property: unknown): string {
  if (!property || typeof property !== 'object') {
    return '';
  }

  const typedProperty = property as {
    title?: Array<{ plain_text?: string }>;
    rich_text?: Array<{ plain_text?: string }>;
    email?: string | null;
    select?: { name?: string } | null;
    date?: { start?: string | null } | null;
  };

  if (typedProperty.title?.length) {
    return typedProperty.title.map((item) => item.plain_text ?? '').join('');
  }

  if (typedProperty.rich_text?.length) {
    return typedProperty.rich_text.map((item) => item.plain_text ?? '').join('');
  }

  if (typedProperty.email) {
    return typedProperty.email;
  }

  if (typedProperty.select?.name) {
    return typedProperty.select.name;
  }

  if (typedProperty.date?.start) {
    return typedProperty.date.start;
  }

  return '';
}

function mapPageToApplication(page: PageObjectResponse): Application {
  const properties = page.properties as Record<string, unknown>;
  const status = getTextContent(properties[notionPropertyNames.status]);
  const appliedAt = getTextContent(properties[notionPropertyNames.appliedAt]) || page.created_time;
  const updatedAt = page.last_edited_time;

  return {
    id: page.id,
    title: getTextContent(properties[notionPropertyNames.title]) || '無題の申請',
    applicantName: getTextContent(properties[notionPropertyNames.applicantName]),
    applicantEmail: getTextContent(properties[notionPropertyNames.applicantEmail]),
    documentType: (getTextContent(properties[notionPropertyNames.documentType]) || 'その他') as Application['documentType'],
    description: getTextContent(properties[notionPropertyNames.description]),
    attachmentInfo: getTextContent(properties[notionPropertyNames.attachmentInfo]),
    status: (APPLICATION_STATUSES.includes(status as ApplicationStatus) ? status : '未承認') as ApplicationStatus,
    appliedAt,
    approverName: getTextContent(properties[notionPropertyNames.approverName]),
    comment: getTextContent(properties[notionPropertyNames.comment]),
    updatedAt,
  };
}

function toRichText(content?: string) {
  return content ? [{ text: { content } }] : [];
}

function buildCreateProperties(input: ApplicationCreateInput, appliedAt: string) {
  return {
    [notionPropertyNames.title]: {
      title: [{ text: { content: input.title } }],
    },
    [notionPropertyNames.applicantName]: {
      rich_text: toRichText(input.applicantName),
    },
    [notionPropertyNames.applicantEmail]: {
      email: input.applicantEmail,
    },
    [notionPropertyNames.documentType]: {
      select: { name: input.documentType },
    },
    [notionPropertyNames.description]: {
      rich_text: toRichText(input.description),
    },
    [notionPropertyNames.status]: {
      select: { name: '未承認' },
    },
    [notionPropertyNames.appliedAt]: {
      date: { start: appliedAt },
    },
    [notionPropertyNames.approverName]: {
      rich_text: [],
    },
    [notionPropertyNames.comment]: {
      rich_text: [],
    },
    [notionPropertyNames.attachmentInfo]: {
      rich_text: toRichText(input.attachmentInfo),
    },
  };
}

export async function listApplications(): Promise<Application[]> {
  if (!notion || !isNotionConfigured) {
    return Array.from(fallbackStore.values()).sort((left, right) =>
      right.appliedAt.localeCompare(left.appliedAt),
    );
  }

  const response = await withRetry<Awaited<ReturnType<Client['databases']['query']>>>(() =>
    notion.databases.query({
      database_id: notionConfig.databaseId,
      page_size: notionConfig.pageSize,
      sorts: [{ property: notionPropertyNames.appliedAt, direction: 'descending' }],
    }),
  );

  return response.results
    .filter(
      (result): result is PageObjectResponse =>
        Boolean(result && typeof result === 'object' && 'properties' in result),
    )
    .map(mapPageToApplication);
}

export async function getApplicationById(id: string): Promise<Application | null> {
  if (!notion || !isNotionConfigured) {
    return fallbackStore.get(id) ?? null;
  }

  const response = await withRetry(() => notion.pages.retrieve({ page_id: id }));
  if (!('properties' in response)) {
    return null;
  }

  return mapPageToApplication(response as PageObjectResponse);
}

export async function createApplication(input: ApplicationCreateInput): Promise<Application> {
  const appliedAt = new Date().toISOString();

  if (!notion || !isNotionConfigured) {
    const id = crypto.randomUUID();
    const created: Application = {
      id,
      title: input.title,
      applicantName: input.applicantName,
      applicantEmail: input.applicantEmail,
      documentType: input.documentType,
      description: input.description,
      attachmentInfo: input.attachmentInfo,
      status: '未承認',
      appliedAt,
      approverName: '',
      comment: '',
      updatedAt: appliedAt,
    };
    fallbackStore.set(id, created);
    await notifyApplicationCreated(created);
    return created;
  }

  const response = await withRetry(() =>
    notion.pages.create({
      parent: { database_id: notionConfig.databaseId },
      properties: buildCreateProperties(input, appliedAt),
    }),
  );

  const created = mapPageToApplication(response as PageObjectResponse);
  await notifyApplicationCreated(created);
  return created;
}

export async function updateApplicationStatus(
  id: string,
  input: ApplicationStatusUpdateInput,
): Promise<Application | null> {
  const existingApplication = await getApplicationById(id);

  if (!existingApplication) {
    return null;
  }

  if (!canTransitionStatus(existingApplication.status, input.status)) {
    throw new Error('許可されていないステータス遷移です。');
  }

  if (!notion || !isNotionConfigured) {
    const updated: Application = {
      ...existingApplication,
      status: input.status,
      approverName: input.approverName ?? existingApplication.approverName,
      comment: input.comment ?? existingApplication.comment,
      updatedAt: new Date().toISOString(),
    };
    fallbackStore.set(id, updated);
    await notifyApplicationStatusChanged(updated);
    return updated;
  }

  const response = await withRetry(() =>
    notion.pages.update({
      page_id: id,
      properties: {
        [notionPropertyNames.status]: {
          select: { name: input.status },
        },
        [notionPropertyNames.approverName]: {
          rich_text: toRichText(input.approverName),
        },
        [notionPropertyNames.comment]: {
          rich_text: toRichText(input.comment),
        },
      },
    }),
  );

  const updated = mapPageToApplication(response as PageObjectResponse);
  await notifyApplicationStatusChanged(updated);
  return updated;
}

export async function deleteApplication(id: string): Promise<boolean> {
  if (!notion || !isNotionConfigured) {
    return fallbackStore.delete(id);
  }

  await withRetry(() => notion.pages.update({ page_id: id, archived: true }));
  return true;
}

export async function syncApplications(): Promise<NotionSyncSummary> {
  const applications = await listApplications();
  return {
    count: applications.length,
    syncedAt: new Date().toISOString(),
    source: notion && isNotionConfigured ? 'notion' : 'memory',
  };
}
