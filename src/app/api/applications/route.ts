import { NextRequest, NextResponse } from 'next/server';
import { createApplication, listApplications } from '@/services/notionService';
import { validateApplicationCreateInput } from '@/utils/validators';

export async function GET() {
  try {
    const applications = await listApplications();
    return NextResponse.json({ data: applications });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '申請一覧の取得に失敗しました。' },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json();
    const errors = validateApplicationCreateInput(payload);

    if (errors.length > 0) {
      return NextResponse.json({ errors }, { status: 400 });
    }

    const application = await createApplication(payload);
    return NextResponse.json({ data: application }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '申請の作成に失敗しました。' },
      { status: 500 },
    );
  }
}
