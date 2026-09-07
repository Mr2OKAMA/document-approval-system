import type { ApplicationStatus } from '@/types/application';

const statusStyles: Record<ApplicationStatus, string> = {
  未承認: 'bg-slate-100 text-slate-700',
  承認中: 'bg-amber-100 text-amber-800',
  完了: 'bg-emerald-100 text-emerald-800',
  却下: 'bg-rose-100 text-rose-800',
};

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[status]}`}>
      {status}
    </span>
  );
}
