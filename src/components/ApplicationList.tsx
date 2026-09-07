'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { StatusBadge } from '@/components/StatusBadge';
import { useApplications } from '@/hooks/useApplications';
import { APPLICATION_STATUSES, DOCUMENT_TYPES } from '@/types/application';

type SortKey = 'title' | 'applicantName' | 'documentType' | 'status' | 'appliedAt';

export function ApplicationList() {
  const router = useRouter();
  const { applications, isLoading, error, refresh } = useApplications();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [documentTypeFilter, setDocumentTypeFilter] = useState<string>('');
  const [sortKey, setSortKey] = useState<SortKey>('appliedAt');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const handleSortChange = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDirection(key === 'appliedAt' ? 'desc' : 'asc');
  };

  const filteredApplications = useMemo(() => {
    const filtered = applications.filter((application) => {
      const matchesStatus = !statusFilter || application.status === statusFilter;
      const matchesDocumentType = !documentTypeFilter || application.documentType === documentTypeFilter;
      return matchesStatus && matchesDocumentType;
    });

    return filtered.sort((left, right) => {
      if (sortKey === 'appliedAt') {
        const compareValue = left.appliedAt.localeCompare(right.appliedAt);
        return sortDirection === 'asc' ? compareValue : compareValue * -1;
      }

      const compareValue = left[sortKey].localeCompare(right[sortKey], 'ja');
      return sortDirection === 'asc' ? compareValue : compareValue * -1;
    });
  }, [applications, documentTypeFilter, sortDirection, sortKey, statusFilter]);

  const renderSortLabel = (label: string, key: SortKey) => {
    const icon = sortKey === key ? (sortDirection === 'asc' ? '↑' : '↓') : '↕';
    return `${label} ${icon}`;
  };

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

      {isLoading ? (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <LoadingSpinner size="sm" />
          読み込み中...
        </div>
      ) : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="px-4 py-3 font-medium">
                <button type="button" onClick={() => handleSortChange('title')} className="hover:text-slate-900">
                  {renderSortLabel('件名', 'title')}
                </button>
              </th>
              <th className="px-4 py-3 font-medium">
                <button
                  type="button"
                  onClick={() => handleSortChange('applicantName')}
                  className="hover:text-slate-900"
                >
                  {renderSortLabel('申請者', 'applicantName')}
                </button>
              </th>
              <th className="px-4 py-3 font-medium">
                <button
                  type="button"
                  onClick={() => handleSortChange('documentType')}
                  className="hover:text-slate-900"
                >
                  {renderSortLabel('書類種別', 'documentType')}
                </button>
              </th>
              <th className="px-4 py-3 font-medium">
                <button type="button" onClick={() => handleSortChange('status')} className="hover:text-slate-900">
                  {renderSortLabel('ステータス', 'status')}
                </button>
              </th>
              <th className="px-4 py-3 font-medium">
                <button
                  type="button"
                  onClick={() => handleSortChange('appliedAt')}
                  className="hover:text-slate-900"
                >
                  {renderSortLabel('申請日時', 'appliedAt')}
                </button>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredApplications.map((application) => (
              <tr
                key={application.id}
                className="cursor-pointer text-slate-700 transition hover:bg-slate-50"
                onClick={() => router.push(`/applications/${application.id}`)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    router.push(`/applications/${application.id}`);
                  }
                }}
                role="button"
                tabIndex={0}
              >
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
                <td className="px-4 py-4">
                  {new Date(application.appliedAt).toLocaleString('ja-JP', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </td>
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
