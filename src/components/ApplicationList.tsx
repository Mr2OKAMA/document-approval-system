'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { StatusBadge } from '@/components/StatusBadge';
import { useApplications } from '@/hooks/useApplications';
import { APPLICATION_STATUSES, DOCUMENT_TYPES } from '@/types/application';

export function ApplicationList() {
  const { applications, isLoading, error, refresh } = useApplications();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [documentTypeFilter, setDocumentTypeFilter] = useState<string>('');

  const filteredApplications = useMemo(() => {
    return applications.filter((application) => {
      const matchesStatus = !statusFilter || application.status === statusFilter;
      const matchesDocumentType = !documentTypeFilter || application.documentType === documentTypeFilter;
      return matchesStatus && matchesDocumentType;
    });
  }, [applications, documentTypeFilter, statusFilter]);

  return (
    <div className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm font-medium text-slate-700">
            ステータス
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3"
            >
              <option value="">すべて</option>
              {APPLICATION_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-sm font-medium text-slate-700">
            書類種別
            <select
              value={documentTypeFilter}
              onChange={(event) => setDocumentTypeFilter(event.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3"
            >
              <option value="">すべて</option>
              {DOCUMENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={refresh}
          className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          再読み込み
        </button>
      </div>

      {isLoading ? <p className="text-sm text-slate-500">読み込み中...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="px-4 py-3 font-medium">件名</th>
              <th className="px-4 py-3 font-medium">申請者</th>
              <th className="px-4 py-3 font-medium">書類種別</th>
              <th className="px-4 py-3 font-medium">ステータス</th>
              <th className="px-4 py-3 font-medium">申請日時</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredApplications.map((application) => (
              <tr key={application.id} className="text-slate-700">
                <td className="px-4 py-4 font-medium text-slate-900">
                  <Link href={`/applications/${application.id}`} className="hover:text-blue-600">
                    {application.title}
                  </Link>
                </td>
                <td className="px-4 py-4">{application.applicantName}</td>
                <td className="px-4 py-4">{application.documentType}</td>
                <td className="px-4 py-4">
                  <StatusBadge status={application.status} />
                </td>
                <td className="px-4 py-4">{new Date(application.appliedAt).toLocaleDateString('ja-JP')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!isLoading && filteredApplications.length === 0 ? (
        <p className="text-sm text-slate-500">条件に一致する申請はありません。</p>
      ) : null}
    </div>
  );
}
