import { ApplicationList } from '@/components/ApplicationList';

export default function ApplicationsListPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">申請一覧</h1>
        <p className="mt-2 text-sm text-slate-600">
          登録済み申請の閲覧、ステータス確認、書類種別・進捗での絞り込みができます。
        </p>
      </div>
      <ApplicationList />
    </div>
  );
}
