import Link from 'next/link';
import type { Application } from '@/types/application';
import { StatusBadge } from '@/components/StatusBadge';

export function DashboardCard({ application }: { application: Application }) {
  return (
    <Link
      href={`/applications/${application.id}`}
      className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="line-clamp-2 text-sm font-semibold text-slate-900">{application.title}</h3>
        <StatusBadge status={application.status} />
      </div>
      <p className="mt-2 text-sm text-slate-600">{application.applicantName}</p>
      <p className="mt-1 text-xs text-slate-500">{application.documentType}</p>
      <p className="mt-2 text-xs text-slate-500">{new Date(application.appliedAt).toLocaleString('ja-JP')}</p>
    </Link>
  );
}
