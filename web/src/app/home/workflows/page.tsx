const DEFAULT_N8N_DEMO_URL = 'http://localhost:5678';

function normalizeEmbedUrl(url: string) {
  const trimmed = url.trim();
  return trimmed || DEFAULT_N8N_DEMO_URL;
}

export default function WorkflowsPage() {
  const n8nDemoUrl = normalizeEmbedUrl(
    import.meta.env.VITE_N8N_DEMO_URL || DEFAULT_N8N_DEMO_URL,
  );

  return (
    <div className="h-full min-h-0 bg-white">
      <iframe
        title="n8n workflow editor demo"
        src={n8nDemoUrl}
        className="h-full min-h-0 w-full border-0"
        allow="clipboard-read; clipboard-write; fullscreen"
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  );
}
