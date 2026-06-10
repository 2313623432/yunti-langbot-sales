export type ModelCategory = 'text' | 'voice' | 'embedding' | 'pdf';

const DASHSCOPE_TTS_PATH = '/services/aigc/multimodal-generation/generation';

function normalizeBaseUrl(baseUrl: string): string {
  return (baseUrl || '').trim().replace(/\/$/, '');
}

function resolveDashscopeTtsUrl(baseUrl: string): string {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) return '';
  if (normalized.includes('multimodal-generation/generation')) {
    return normalized;
  }
  if (normalized.endsWith('/api/v1')) {
    return `${normalized}${DASHSCOPE_TTS_PATH}`;
  }
  return normalized;
}

function resolveVolcengineTtsUrl(baseUrl: string): string {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) return '';
  if (normalized.endsWith('/api/v1/tts')) {
    return normalized;
  }
  return `${normalized}/api/v1/tts`;
}

export function resolveTextRequestUrl(
  requester: string,
  baseUrl: string,
): string {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) return '-';

  if (normalized.includes('/chat/completions')) {
    return normalized;
  }

  const requesterName = (requester || '').toLowerCase();
  if (requesterName === 'anthropic-messages') {
    if (normalized.endsWith('/v1/messages')) {
      return normalized;
    }
    return `${normalized}/v1/messages`;
  }
  if (requesterName === 'ollama-chat') {
    return `${normalized}/api/chat`;
  }

  return `${normalized}/chat/completions`;
}

export function resolveEmbeddingRequestUrl(
  requester: string,
  baseUrl: string,
): string {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) return '-';

  if (normalized.includes('/embeddings') || normalized.endsWith('/embed')) {
    return normalized;
  }

  const requesterName = (requester || '').toLowerCase();
  if (requesterName === 'ollama-chat') {
    return `${normalized}/api/embed`;
  }

  return `${normalized}/embeddings`;
}

export function resolveVoiceRequestUrl(
  requester: string,
  baseUrl: string,
): string {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) return '-';

  const requesterName = (requester || '').toLowerCase();

  if (requesterName === 'azure-tts') {
    return `${normalized}/cognitiveservices/v1`;
  }
  if (requesterName === 'elevenlabs-tts') {
    return `${normalized}/text-to-speech/{voice_id}`;
  }
  if (requesterName === 'volcengine-tts') {
    return resolveVolcengineTtsUrl(normalized);
  }
  if (
    requesterName === 'bailian-chat-completions' ||
    requesterName === 'dashscope-tts' ||
    normalized.includes('dashscope.aliyuncs.com')
  ) {
    return resolveDashscopeTtsUrl(normalized);
  }
  if (
    requesterName === 'zhipuai-chat-completions' ||
    normalized.includes('bigmodel.cn')
  ) {
    return `${normalized}/audio/speech`;
  }
  if (normalized.includes('minimax')) {
    return `${normalized}/v1/t2a_v2`;
  }
  if (normalized.endsWith('/v1')) {
    return `${normalized}/audio/speech`;
  }

  return baseUrl;
}

export function resolvePdfRequestUrl(
  requester: string,
  baseUrl: string,
): string {
  const rawBaseUrl = (baseUrl || '').trim();
  const normalized = normalizeBaseUrl(rawBaseUrl);
  if (!normalized) return '-';

  const requesterName = (requester || '').toLowerCase();
  if (requesterName === 'builtin-pdf-parse') {
    return rawBaseUrl;
  }
  if (requesterName === 'mineru-cloud') {
    return `${normalized}/file-urls/batch`;
  }
  if (requesterName === 'paddleocr-vl') {
    return rawBaseUrl;
  }

  return rawBaseUrl;
}

export function providerRequestUrl(
  category: ModelCategory,
  requester: string,
  baseUrl: string,
): string {
  if (!baseUrl) return '-';

  switch (category) {
    case 'voice':
      return resolveVoiceRequestUrl(requester, baseUrl);
    case 'embedding':
      return resolveEmbeddingRequestUrl(requester, baseUrl);
    case 'pdf':
      return resolvePdfRequestUrl(requester, baseUrl);
    default:
      return resolveTextRequestUrl(requester, baseUrl);
  }
}
