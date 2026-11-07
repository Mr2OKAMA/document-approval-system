'use client';

import { useParams } from 'next/navigation';
import { ApplicationDetail } from '@/components/ApplicationDetail';

export default function ApplicationDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  if (!id) {
    return null;
  }

  return <ApplicationDetail id={id} />;
}
