import type { ApplicationStatus } from '@/types/application';

const statusStyles: Record<ApplicationStatus, string> = {
  未承認: 'bg-red-100 text-red-800',
  承認中: 'bg-yellow-100 text-yellow-800',
  完了: 'bg-green-100 text-green-800',
  却下: 'bg-gray-100 text-gray-800',
};

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[status]}`}>
      {status}
    </span>
  );
}
