import Link from 'next/link';

const navItems = [
  { href: '/', label: 'ダッシュボード' },
  { href: '/applications', label: '新規申請' },
  { href: '/applications/list', label: '申請一覧' },
];

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200 lg:block">
      <nav className="space-y-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="block rounded-xl px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 hover:text-slate-900"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
