import { NextResponse } from 'next/server';
import { syncApplications } from '@/services/notionService';

export async function GET() {
  try {
    const result = await syncApplications();
    return NextResponse.json({ data: result });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Notion 同期に失敗しました。' },
      { status: 500 },
    );
  }
}

export const POST = GET;
