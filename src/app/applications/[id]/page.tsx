import { notFound } from 'next/navigation';
import { StatusBadge } from '@/components/StatusBadge';
import { getApplicationById } from '@/services/notionService';

export default async function ApplicationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const application = await getApplicationById(id);

  if (!application) {
    notFound();
  }

  return (
    <div className="space-y-6 rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-slate-500">申請ID: {application.id}</p>
          <h1 className="text-2xl font-bold text-slate-900">{application.title}</h1>
        </div>
        <StatusBadge status={application.status} />
      </div>

      <dl className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-slate-50 p-4">
          <dt className="text-sm font-medium text-slate-500">申請者</dt>
          <dd className="mt-1 text-sm text-slate-900">{application.applicantName}</dd>
          <dd className="text-sm text-slate-500">{application.applicantEmail}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-4">
          <dt className="text-sm font-medium text-slate-500">書類種別</dt>
          <dd className="mt-1 text-sm text-slate-900">{application.documentType}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-4">
          <dt className="text-sm font-medium text-slate-500">承認者</dt>
          <dd className="mt-1 text-sm text-slate-900">{application.approverName || '未設定'}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-4">
          <dt className="text-sm font-medium text-slate-500">申請日時</dt>
          <dd className="mt-1 text-sm text-slate-900">
            {new Date(application.appliedAt).toLocaleString('ja-JP')}
          </dd>
        </div>
      </dl>

      <div className="rounded-xl bg-slate-50 p-4">
        <h2 className="text-sm font-medium text-slate-500">申請内容</h2>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-900">{application.description}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-slate-50 p-4">
          <h2 className="text-sm font-medium text-slate-500">添付ファイル情報</h2>
          <p className="mt-2 text-sm text-slate-900">{application.attachmentInfo || 'なし'}</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-4">
          <h2 className="text-sm font-medium text-slate-500">コメント</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm text-slate-900">{application.comment || 'なし'}</p>
        </div>
      </div>
    </div>
  );
}
