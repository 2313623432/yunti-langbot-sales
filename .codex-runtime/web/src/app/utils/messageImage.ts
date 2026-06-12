import { httpClient } from '@/app/infra/http/HttpClient';
import type { Image } from '@/app/infra/entities/message';

export function getMessageImageUrl(image: Pick<Image, 'url' | 'base64' | 'path'>): string {
  if (image.url) {
    return image.url;
  }
  if (image.base64) {
    return image.base64;
  }
  if (!image.path) {
    return '';
  }

  const baseUrl = httpClient.getBaseUrl();
  const prefix = baseUrl === '/' ? '' : baseUrl.replace(/\/$/, '');
  const encodedPath = image.path.split('/').map(encodeURIComponent).join('/');
  return `${prefix}/api/v1/files/image/${encodedPath}`;
}
