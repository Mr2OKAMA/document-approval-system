'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { DOCUMENT_TYPES, type ApplicationCreateInput } from '@/types/application';

const initialState: ApplicationCreateInput = {
  title: '',
  applicantName: '',
  applicantEmail: '',
  documentType: '稟議書',
  description: '',
  attachmentInfo: '',
};

export function ApplicationForm() {
  const router = useRouter();
  const [formData, setFormData] = useState<ApplicationCreateInput>(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch('/api/applications', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.errors?.join(' ') || result.error || '申請に失敗しました。');
      }

      setFormData(initialState);
      router.push('/applications/list');
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '申請に失敗しました。');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
      <div className="grid gap-6 md:grid-cols-2">
        <label className="space-y-2 text-sm font-medium text-slate-700">
          件名
          <input
            name="title"
            value={formData.title}
            onChange={handleChange}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500"
            placeholder="例: 契約書レビュー申請"
            required
          />
        </label>

        <label className="space-y-2 text-sm font-medium text-slate-700">
          書類種別
          <select
            name="documentType"
            value={formData.documentType}
            onChange={handleChange}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500"
          >
            {DOCUMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2 text-sm font-medium text-slate-700">
          申請者名
          <input
            name="applicantName"
            value={formData.applicantName}
            onChange={handleChange}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500"
            placeholder="山田 太郎"
            required
          />
        </label>

        <label className="space-y-2 text-sm font-medium text-slate-700">
          申請者メールアドレス
          <input
            type="email"
            name="applicantEmail"
            value={formData.applicantEmail}
            onChange={handleChange}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500"
            placeholder="user@example.com"
            required
          />
        </label>
      </div>

      <label className="block space-y-2 text-sm font-medium text-slate-700">
        申請内容
        <textarea
          name="description"
          value={formData.description}
          onChange={handleChange}
          rows={6}
          className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500"
          placeholder="申請の背景、目的、承認してほしい内容を入力してください。"
          required
        />
      </label>

      <label className="block space-y-2 text-sm font-medium text-slate-700">
        添付ファイル情報
        <input
          name="attachmentInfo"
          value={formData.attachmentInfo}
          onChange={handleChange}
          className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500"
          placeholder="例: 見積書.pdf / 共有ドライブURL"
        />
      </label>

      {error ? <p className="text-sm font-medium text-rose-600">{error}</p> : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? '送信中...' : '申請を登録する'}
      </button>
    </form>
  );
}
