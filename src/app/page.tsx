'use client';

import Link from 'next/link';
import { DashboardCard } from '@/components/DashboardCard';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { useApplications } from '@/hooks/useApplications';

const summaryItems = ['未承認', '承認中', '完了', '却下'] as const;

export default function HomePage() {
  const { applications, isLoading, error } = useApplications();
  const latestApplications = applications.slice(0, 5);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
        <p className="text-sm font-medium text-blue-600">Document Approval System</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">
          社内向けの書類申請・承認・管理WEBアプリ
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-600">
          Next.js ベースのフロントエンドと API から Notion データベースを操作し、申請フォーム、一覧表示、
          ステータス管理をひとつのアプリで扱える構成です。Microsoft Teams 通知は Webhook 設定時に利用できます。
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {summaryItems.map((status) => (
          <div key={status} className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <p className="text-sm font-medium text-slate-600">{status}</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {applications.filter((application) => application.status === status).length}
            </p>
          </div>
        ))}
      </section>

      <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-900">最新5件の申請</h2>
          <Link href="/applications/list" className="text-sm font-medium text-blue-600 hover:text-blue-700">
            すべて見る
          </Link>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <LoadingSpinner size="sm" />
            読み込み中...
          </div>
        ) : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        {!isLoading && latestApplications.length === 0 ? (
          <p className="text-sm text-slate-500">申請データがありません。</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {latestApplications.map((application) => (
              <DashboardCard key={application.id} application={application} />
            ))}
          </div>
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/applications"
          className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <h2 className="text-lg font-semibold text-slate-900">新規申請</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">新しい申請を作成します。</p>
        </Link>
        <Link
          href="/applications/list"
          className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <h2 className="text-lg font-semibold text-slate-900">一覧表示</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">申請一覧を確認します。</p>
        </Link>
      </section>
    </div>
  );
}
