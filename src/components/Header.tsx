import Link from 'next/link';

const navItems = [
  { href: '/', label: 'ダッシュボード' },
  { href: '/applications', label: '新規申請' },
  { href: '/applications/list', label: '申請一覧' },
];

export function Header() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-600">
              Internal Workflow
            </p>
            <h1 className="text-lg font-semibold text-slate-900">Document Approval System</h1>
          </div>
          <p className="text-sm text-slate-500 lg:hidden">Notion / Teams 連携対応</p>
        </div>

        <nav className="flex flex-wrap items-center gap-2">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 hover:text-slate-900"
            >
              {item.label}
            </Link>
          ))}
          <p className="hidden text-sm text-slate-500 lg:block">Notion / Teams 連携対応</p>
        </nav>
      </div>
    </header>
  );
}
