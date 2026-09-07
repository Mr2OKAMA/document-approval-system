export const APPLICATION_STATUSES = ['未承認', '承認中', '完了', '却下'] as const;
export const DOCUMENT_TYPES = ['稟議書', '経費申請', '契約書', 'その他'] as const;

export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number];
export type DocumentType = (typeof DOCUMENT_TYPES)[number];

export interface Application {
  id: string;
  title: string;
  applicantName: string;
  applicantEmail: string;
  documentType: DocumentType;
  description: string;
  attachmentInfo?: string;
  status: ApplicationStatus;
  appliedAt: string;
  approverName?: string;
  comment?: string;
  updatedAt: string;
}

export interface ApplicationCreateInput {
  title: string;
  applicantName: string;
  applicantEmail: string;
  documentType: DocumentType;
  description: string;
  attachmentInfo?: string;
}

export interface ApplicationStatusUpdateInput {
  status: ApplicationStatus;
  approverName?: string;
  comment?: string;
}
