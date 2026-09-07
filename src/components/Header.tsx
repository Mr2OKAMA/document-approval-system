export function Header() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-600">
            Internal Workflow
          </p>
          <h1 className="text-lg font-semibold text-slate-900">Document Approval System</h1>
        </div>
        <p className="text-sm text-slate-500">Notion / Teams 連携対応</p>
      </div>
    </header>
  );
}
