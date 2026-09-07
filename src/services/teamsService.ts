import axios from 'axios';
import type { Application } from '@/types/application';

const webhookUrl = process.env.MICROSOFT_TEAMS_WEBHOOK_URL;

async function postToTeams(title: string, application: Application) {
  if (!webhookUrl) {
    return { sent: false, reason: 'webhook-not-configured' as const };
  }

  await axios.post(webhookUrl, {
    '@type': 'MessageCard',
    '@context': 'https://schema.org/extensions',
    summary: title,
    themeColor: '0078D4',
    title,
    sections: [
      {
        facts: [
          { name: '件名', value: application.title },
          { name: '申請者', value: application.applicantName },
          { name: '書類種別', value: application.documentType },
          { name: 'ステータス', value: application.status },
        ],
        text: application.description,
      },
    ],
  });

  return { sent: true as const };
}

export async function notifyApplicationCreated(application: Application) {
  return postToTeams('新しい申請が登録されました', application);
}

export async function notifyApplicationStatusChanged(application: Application) {
  return postToTeams('申請ステータスが更新されました', application);
}
