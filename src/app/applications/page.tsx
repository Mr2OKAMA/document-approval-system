import { ApplicationForm } from '@/components/ApplicationForm';

export default function ApplicationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">新規申請フォーム</h1>
        <p className="mt-2 text-sm text-slate-600">
          書類申請に必要な情報を入力すると、Notion データベースに申請データを作成します。
        </p>
      </div>
      <ApplicationForm />
    </div>
  );
}
