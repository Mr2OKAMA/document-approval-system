import {
  APPLICATION_STATUSES,
  DOCUMENT_TYPES,
  type ApplicationStatus,
  type ApplicationCreateInput,
  type ApplicationStatusUpdateInput,
} from '@/types/application';

const allowedStatusTransitions: Record<ApplicationStatus, ApplicationStatus[]> = {
  未承認: ['未承認', '承認中'],
  承認中: ['承認中', '完了', '却下'],
  完了: ['完了'],
  却下: ['却下'],
};

export function validateApplicationCreateInput(input: Partial<ApplicationCreateInput>): string[] {
  const errors: string[] = [];

  if (!input.title?.trim()) {
    errors.push('件名は必須です。');
  }

  if (!input.applicantName?.trim()) {
    errors.push('申請者名は必須です。');
  }

  if (!input.applicantEmail?.trim()) {
    errors.push('申請者メールアドレスは必須です。');
  }

  if (input.applicantEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.applicantEmail)) {
    errors.push('申請者メールアドレスの形式が不正です。');
  }

  if (!input.description?.trim()) {
    errors.push('申請内容は必須です。');
  }

  if (!input.documentType || !DOCUMENT_TYPES.includes(input.documentType)) {
    errors.push('書類種別が不正です。');
  }

  return errors;
}

export function validateApplicationStatusUpdateInput(
  input: Partial<ApplicationStatusUpdateInput>,
): string[] {
  const errors: string[] = [];

  if (!input.status || !APPLICATION_STATUSES.includes(input.status)) {
    errors.push('ステータスが不正です。');
  }

  return errors;
}

export function canTransitionStatus(
  currentStatus: ApplicationStatus,
  nextStatus: ApplicationStatus,
): boolean {
  return allowedStatusTransitions[currentStatus].includes(nextStatus);
}
