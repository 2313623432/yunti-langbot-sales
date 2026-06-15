import type { ReactNode } from 'react';
import { FileText, ImageIcon, Link2, Volume2 } from 'lucide-react';

import type { SalesMessageComponent } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';

function browserSafeMediaSource(value?: unknown): string {
  const source = String(value || '').trim();
  if (!source) return '';
  if (source.startsWith('file://')) return '';
  if (/^[A-Za-z]:[\\/]/.test(source)) return '';
  if (source.startsWith('\\\\')) return '';
  return source;
}

function mediaSource(component: {
  url?: string;
  base64?: string;
  path?: string;
  raw?: Record<string, unknown>;
}): string {
  const candidates = [
    component.url,
    component.base64,
    rawValue(component.raw, [
      'image_url',
      'voice_url',
      'audio_url',
      'file_url',
      'download_url',
      'url',
    ]),
    rawValue(component.raw, [
      'base64',
      'data',
      'image_base64',
      'voice_base64',
      'audio_base64',
      'file_base64',
    ]),
    component.path,
    rawValue(component.raw, ['path']),
  ];
  for (const candidate of candidates) {
    const source = browserSafeMediaSource(candidate);
    if (source) return source;
  }
  return '';
}

function rawValue(
  raw: Record<string, unknown> | undefined,
  keys: string[],
): string {
  for (const key of keys) {
    const value = raw?.[key];
    if (value !== undefined && value !== null && value !== '') {
      return String(value);
    }
  }
  return '';
}

export function SalesMessageComponents({
  components,
  compact = false,
}: {
  components: SalesMessageComponent[];
  compact?: boolean;
}) {
  if (!components.length) {
    return <span className="text-[#8a93a5]">[空消息]</span>;
  }

  return (
    <div className="space-y-2">
      {components.map((component, index) => (
        <SalesMessageComponentView
          key={`${component.kind}-${index}`}
          component={component}
          compact={compact}
        />
      ))}
    </div>
  );
}

function SalesMessageComponentView({
  component,
  compact,
}: {
  component: SalesMessageComponent;
  compact: boolean;
}) {
  if (component.kind === 'text') {
    return (
      <div className="whitespace-pre-wrap break-words">{component.text}</div>
    );
  }

  if (component.kind === 'image') {
    const src = mediaSource(component);
    if (src) {
      return (
        <a href={src} target="_blank" rel="noreferrer" className="block">
          <img
            src={src}
            alt={component.name || '聊天图片'}
            className={cn(
              'max-w-full rounded-md border border-black/5 object-cover',
              compact ? 'max-h-20' : 'max-h-72',
            )}
          />
        </a>
      );
    }
    return (
      <AttachmentCard
        icon={<ImageIcon className="size-4" />}
        title="图片"
        detail={
          component.name ||
          rawValue(component.raw, ['image_id', 'file_id']) ||
          '图片资源不可直接预览'
        }
      />
    );
  }

  if (component.kind === 'voice') {
    const src = mediaSource(component);
    if (src) {
      return (
        <div className="min-w-[220px] rounded-md bg-black/5 px-3 py-2">
          <div className="mb-2 flex items-center gap-2 text-sm">
            <Volume2 className="size-4" />
            <span>{component.length ? `${component.length}s` : '语音消息'}</span>
          </div>
          <audio controls src={src} className="h-9 w-full" />
        </div>
      );
    }
    return (
      <AttachmentCard
        icon={<Volume2 className="size-4" />}
        title="语音"
        detail={
          rawValue(component.raw, ['voice_id', 'file_id', 'duration']) ||
          '语音资源不可直接播放'
        }
      />
    );
  }

  if (component.kind === 'file') {
    const src = mediaSource(component);
    const card = (
      <AttachmentCard
        icon={<FileText className="size-4" />}
        title={component.name || '文件'}
        detail={component.available ? '点击打开文件' : '文件资源不可直接打开'}
      />
    );
    return src ? (
      <a href={src} target="_blank" rel="noreferrer">
        {card}
      </a>
    ) : (
      card
    );
  }

  if (component.kind === 'link') {
    return (
      <a
        href={component.url || '#'}
        target="_blank"
        rel="noreferrer"
        className="block rounded-md border border-black/10 bg-white/70 p-3 text-inherit"
      >
        <div className="flex items-center gap-2 font-medium">
          <Link2 className="size-4" />
          <span>{component.title || '链接'}</span>
        </div>
        {component.description && (
          <div className="mt-1 line-clamp-2 text-sm opacity-80">
            {component.description}
          </div>
        )}
        {component.url && (
          <div className="mt-2 truncate text-xs opacity-70">
            {component.url}
          </div>
        )}
      </a>
    );
  }

  if (component.kind === 'quote') {
    return (
      <blockquote className="border-l-2 border-black/20 pl-3 text-sm opacity-80">
        {component.text || '引用消息'}
      </blockquote>
    );
  }

  return (
    <AttachmentCard
      icon={<FileText className="size-4" />}
      title={component.label || component.type || '附件'}
      detail={component.type || '未知消息组件'}
    />
  );
}

function AttachmentCard({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="flex min-w-[180px] items-center gap-3 rounded-md border border-black/10 bg-white/70 px-3 py-2">
      <div className="flex size-8 items-center justify-center rounded-md bg-black/5">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{title}</div>
        <div className="truncate text-xs opacity-70">{detail}</div>
      </div>
    </div>
  );
}
