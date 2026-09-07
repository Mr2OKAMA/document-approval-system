'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { StatusBadge } from '@/components/StatusBadge';
import type { Application, ApplicationStatus } from '@/types/application';

const nextStatusMap: Record<ApplicationStatus, ApplicationStatus[]> = {
  未承認: ['承認中'],
  承認中: ['完了', '却下'],
  完了: [],
  却下: [],
};

export function ApplicationDetail({ id }: { id: string }) {
  const [application, setApplication] = useState<Application | null>(null);
  const [approverName, setApproverName] = useState('');
  const [comment, setComment] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/applications/${id}`, { cache: 'no-store' });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || '申請詳細の取得に失敗しました。');
      }

      const data = result.data as Application;
      setApplication(data);
      setApproverName(data.approverName ?? '');
      setComment('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '申請詳細の取得に失敗しました。');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadDetail();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadDetail]);

  const updateApplication = useCallback(
    async (nextStatus: ApplicationStatus, nextComment?: string) => {
      if (!application) {
        return;
      }

      setIsUpdating(true);
      setError(null);
      setMessage(null);

      try {
        const response = await fetch(`/api/applications/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status: nextStatus,
            approverName: approverName.trim() || application.approverName || '',
            comment: nextComment ?? application.comment ?? '',
          }),
        });
        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.errors?.join(' ') || result.error || '更新に失敗しました。');
        }

        const updated = result.data as Application;
        setApplication(updated);
        setApproverName(updated.approverName ?? '');
        setComment('');
        setMessage('申請情報を更新しました。');
      } catch (updateError) {
        setError(updateError instanceof Error ? updateError.message : '更新に失敗しました。');
      } finally {
        setIsUpdating(false);
      }
    },
    [application, approverName, id],
  );

  const nextStatuses = useMemo(() => {
    if (!application) {
      return [];
    }
    return nextStatusMap[application.status];
  }, [application]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
        <LoadingSpinner />
        <p className="text-sm text-slate-600">読み込み中...</p>
      </div>
    );
  }

  if (error && !application) {
    return (
      <div className="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
        <p className="text-sm text-rose-600">{error}</p>
      </div>
    );
  }

  if (!application) {
    return null;
  }

  const approvalDatetime =
    application.status === '完了' || application.status === '却下'
      ? new Date(application.updatedAt).toLocaleString('ja-JP')
      : '未承認';

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
          <dt className="text-sm font-medium text-slate-500">申請日時</dt>
          <dd className="mt-1 text-sm text-slate-900">{new Date(application.appliedAt).toLocaleString('ja-JP')}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 p-4">
          <dt className="text-sm font-medium text-slate-500">承認者 / 承認日時</dt>
          <dd className="mt-1 text-sm text-slate-900">{application.approverName || '未設定'}</dd>
          <dd className="text-sm text-slate-500">{approvalDatetime}</dd>
        </div>
      </dl>

      <div className="rounded-xl bg-slate-50 p-4">
        <h2 className="text-sm font-medium text-slate-500">申請内容</h2>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-900">{application.description}</p>
      </div>

      <div className="rounded-xl bg-slate-50 p-4">
        <h2 className="text-sm font-medium text-slate-500">添付ファイル情報</h2>
        <p className="mt-2 text-sm text-slate-900">{application.attachmentInfo || 'なし'}</p>
      </div>

      <div className="space-y-4 rounded-xl bg-slate-50 p-4">
        <h2 className="text-sm font-medium text-slate-500">コメント</h2>
        <p className="whitespace-pre-wrap text-sm text-slate-900">{application.comment || 'なし'}</p>

        <label className="block space-y-2 text-sm font-medium text-slate-700">
          承認者名
          <input
            value={approverName}
            onChange={(event) => setApproverName(event.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3"
            placeholder="承認者名を入力"
          />
        </label>

        <label className="block space-y-2 text-sm font-medium text-slate-700">
          追加コメント
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            rows={4}
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3"
            placeholder="コメントを入力"
          />
        </label>

        <div className="flex flex-wrap gap-3">
          {nextStatuses.map((status) => (
            <button
              key={status}
              type="button"
              disabled={isUpdating}
              onClick={() => void updateApplication(status, comment.trim() || application.comment || '')}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {status}に更新
            </button>
          ))}

          <button
            type="button"
            disabled={isUpdating || !comment.trim()}
            onClick={() => void updateApplication(application.status, comment.trim())}
            className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            コメントを追加
          </button>
        </div>
      </div>

      {isUpdating ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <LoadingSpinner size="sm" />
          更新中...
        </div>
      ) : null}
      {message ? <p className="text-sm text-green-700">{message}</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
    </div>
  );
}
