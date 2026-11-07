import { NextRequest, NextResponse } from 'next/server';
import { deleteApplication, getApplicationById, updateApplicationStatus } from '@/services/notionService';
import { validateApplicationStatusUpdateInput } from '@/utils/validators';

export async function GET(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const application = await getApplicationById(id);

    if (!application) {
      return NextResponse.json({ error: '申請が見つかりません。' }, { status: 404 });
    }

    return NextResponse.json({ data: application });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '申請詳細の取得に失敗しました。' },
      { status: 500 },
    );
  }
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const payload = await request.json();
    const errors = validateApplicationStatusUpdateInput(payload);

    if (errors.length > 0) {
      return NextResponse.json({ errors }, { status: 400 });
    }

    const updated = await updateApplicationStatus(id, payload);

    if (!updated) {
      return NextResponse.json({ error: '申請が見つかりません。' }, { status: 404 });
    }

    return NextResponse.json({ data: updated });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'ステータス更新に失敗しました。';
    return NextResponse.json(
      { error: message },
      { status: message === '許可されていないステータス遷移です。' ? 400 : 500 },
    );
  }
}

export async function DELETE(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const deleted = await deleteApplication(id);

    if (!deleted) {
      return NextResponse.json({ error: '申請が見つかりません。' }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '申請の削除に失敗しました。' },
      { status: 500 },
    );
  }
}
