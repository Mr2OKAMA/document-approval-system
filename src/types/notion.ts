export interface NotionPropertyNames {
  title: string;
  applicantName: string;
  applicantEmail: string;
  documentType: string;
  description: string;
  status: string;
  appliedAt: string;
  approverName: string;
  comment: string;
  attachmentInfo: string;
}

export interface NotionSyncSummary {
  count: number;
  syncedAt: string;
  source: 'notion' | 'memory';
}
