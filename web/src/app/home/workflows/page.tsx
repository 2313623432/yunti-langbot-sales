import { useMemo, useState } from 'react';
import { ExternalLink, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';

const DEFAULT_N8N_DEMO_URL = 'https://jiushi.app.n8n.cloud/workflow/new';

function normalizeEmbedUrl(url: string) {
  const trimmed = url.trim();
  return trimmed || DEFAULT_N8N_DEMO_URL;
}

function getN8nHost(url: string) {
  try {
    return new URL(url).host;
  } catch {
    return '';
  }
}

function isN8nCloudUrl(url: string) {
  return getN8nHost(url).endsWith('.n8n.cloud');
}

export default function WorkflowsPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const n8nDemoUrl = normalizeEmbedUrl(
    import.meta.env.VITE_N8N_DEMO_URL || DEFAULT_N8N_DEMO_URL,
  );
  const n8nHost = useMemo(() => getN8nHost(n8nDemoUrl), [n8nDemoUrl]);
  const isCloudEmbed = useMemo(() => isN8nCloudUrl(n8nDemoUrl), [n8nDemoUrl]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-sm font-medium text-slate-900">n8n 工作流</span>
          {n8nHost && (
            <span className="truncate text-xs text-slate-500">{n8nHost}</span>
          )}
          {isCloudEmbed && (
            <span className="hidden rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-700 md:inline">
              n8n Cloud 登录态可能受浏览器限制
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            onClick={() => window.open(n8nDemoUrl, '_blank', 'noopener')}
          >
            <ExternalLink className="size-3.5" />
            打开 n8n
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            onClick={() => setReloadKey((current) => current + 1)}
          >
            <RefreshCw className="size-3.5" />
            刷新
          </Button>
        </div>
      </div>
      <iframe
        key={reloadKey}
        title="n8n workflow editor demo"
        src={n8nDemoUrl}
        className="min-h-0 flex-1 border-0"
        allow="clipboard-read; clipboard-write; fullscreen; storage-access"
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  );
}
