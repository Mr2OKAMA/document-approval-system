import type { NotionPropertyNames } from '@/types/notion';

export const notionPropertyNames: NotionPropertyNames = {
  title: 'Title',
  applicantName: 'ApplicantName',
  applicantEmail: 'ApplicantEmail',
  documentType: 'DocumentType',
  description: 'Description',
  status: 'Status',
  appliedAt: 'AppliedAt',
  approverName: 'ApproverName',
  comment: 'Comment',
  attachmentInfo: 'AttachmentInfo',
};

export const notionConfig = {
  apiKey: process.env.NOTION_API_KEY ?? '',
  databaseId: process.env.NOTION_DATABASE_ID ?? '',
  pageSize: Number(process.env.NOTION_PAGE_SIZE ?? '50'),
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? 'Document Approval System',
};

export const isNotionConfigured = Boolean(notionConfig.apiKey && notionConfig.databaseId);
