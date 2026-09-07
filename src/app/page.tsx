import Link from 'next/link';

const cards = [
  {
    href: '/applications',
    title: '新規申請',
    description: '書類種別や説明、添付ファイル情報を入力して申請を登録します。',
  },
  {
    href: '/applications/list',
    title: '申請一覧',
    description: '申請の一覧表示、ステータスや書類種別による絞り込みを行います。',
  },
  {
    href: '/api/notion/sync',
    title: 'Notion 同期 API',
    description: 'Notion データベースとの同期状態を確認する API エンドポイントです。',
  },
];

export default function HomePage() {
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

      <section className="grid gap-4 md:grid-cols-3">
        {cards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md"
          >
            <h2 className="text-lg font-semibold text-slate-900">{card.title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">{card.description}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
