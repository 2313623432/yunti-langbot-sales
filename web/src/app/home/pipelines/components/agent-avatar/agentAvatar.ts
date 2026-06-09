import { httpClient } from '@/app/infra/http/HttpClient';

export const PRESET_AGENT_AVATARS = [
  { label: '蓝色顾问', src: '/agent-avatars/sales-agent-blue.png' },
  { label: '数据顾问', src: '/agent-avatars/sales-agent-data.png' },
  { label: '跟进顾问', src: '/agent-avatars/sales-agent-chat.png' },
];

export const DEFAULT_AGENT_AVATAR = PRESET_AGENT_AVATARS[0].src;

export function agentAvatarUrl(avatar?: string) {
  const normalizedAvatar = avatar?.trim();
  if (!normalizedAvatar) {
    return DEFAULT_AGENT_AVATAR;
  }
  if (
    normalizedAvatar.startsWith('/') ||
    normalizedAvatar.startsWith('http://') ||
    normalizedAvatar.startsWith('https://') ||
    normalizedAvatar.startsWith('data:') ||
    normalizedAvatar.startsWith('blob:')
  ) {
    return normalizedAvatar;
  }

  const baseUrl = httpClient.getBaseUrl();
  const prefix = baseUrl === '/' ? '' : baseUrl.replace(/\/$/, '');
  const encodedKey = normalizedAvatar.split('/').map(encodeURIComponent).join('/');
  return `${prefix}/api/v1/files/image/${encodedKey}`;
}
