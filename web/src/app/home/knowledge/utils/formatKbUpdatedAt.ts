import { TFunction } from 'i18next';

export function formatKbUpdatedAt(
  updatedAt: string | undefined,
  t: TFunction,
): string {
  if (!updatedAt) return '';

  const date = new Date(updatedAt);
  if (Number.isNaN(date.getTime())) return '';

  const now = new Date();
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  const startOfUpdated = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  const diffDays = Math.floor(
    (startOfToday.getTime() - startOfUpdated.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diffDays <= 0) {
    return `${t('knowledge.updateTime')}${t('knowledge.today')}`;
  }

  return `${t('knowledge.updateTime')}${diffDays}${t('knowledge.daysAgo')}`;
}
