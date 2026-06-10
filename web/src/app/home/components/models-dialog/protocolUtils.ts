export type ProviderProtocol = 'openai' | 'claude' | 'gemini';

export const PROVIDER_PROTOCOLS: ProviderProtocol[] = [
  'openai',
  'claude',
  'gemini',
];

const DEFAULT_REQUESTER_BY_PROTOCOL: Record<ProviderProtocol, string> = {
  openai: 'openai-chat-completions',
  claude: 'anthropic-messages',
  gemini: 'gemini-chat-completions',
};

const DEFAULT_BASE_URL_BY_PROTOCOL: Record<ProviderProtocol, string> = {
  openai: 'https://api.openai.com/v1',
  claude: 'https://api.anthropic.com',
  gemini: 'https://generativelanguage.googleapis.com/v1beta/openai',
};

const CLAUDE_REQUESTERS = new Set(['anthropic-messages']);
const GEMINI_REQUESTERS = new Set(['gemini-chat-completions']);

export function getRequesterForProtocol(protocol: ProviderProtocol): string {
  return DEFAULT_REQUESTER_BY_PROTOCOL[protocol];
}

export function getDefaultBaseUrlForProtocol(protocol: ProviderProtocol): string {
  return DEFAULT_BASE_URL_BY_PROTOCOL[protocol];
}

export function inferProtocolFromRequester(
  requester: string,
  providerUuid?: string,
): ProviderProtocol {
  if (CLAUDE_REQUESTERS.has(requester)) {
    return 'claude';
  }
  if (GEMINI_REQUESTERS.has(requester)) {
    return 'gemini';
  }

  const normalizedUuid = (providerUuid || '').toLowerCase();
  const normalizedRequester = (requester || '').toLowerCase();
  if (
    normalizedUuid.includes('minimax') ||
    normalizedRequester.includes('minimax')
  ) {
    return 'claude';
  }

  return 'openai';
}

export function resolveProviderProtocol(
  provider: {
    protocol?: ProviderProtocol;
    requester?: string;
    uuid?: string;
  },
): ProviderProtocol {
  if (provider.protocol && PROVIDER_PROTOCOLS.includes(provider.protocol)) {
    return provider.protocol;
  }
  return inferProtocolFromRequester(
    provider.requester || '',
    provider.uuid,
  );
}

export function getProtocolLabelKey(protocol: ProviderProtocol): string {
  return `models.protocol.${protocol}`;
}
