'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Application } from '@/types/application';

export function useApplications() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadApplications = useCallback(async (showLoading: boolean) => {
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const response = await fetch('/api/applications', { cache: 'no-store' });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || '申請データの取得に失敗しました。');
      }

      setApplications(result.data);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : '申請データの取得に失敗しました。');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    await loadApplications(true);
  }, [loadApplications]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadApplications(false);
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadApplications]);

  return {
    applications,
    isLoading,
    error,
    refresh,
  };
}
