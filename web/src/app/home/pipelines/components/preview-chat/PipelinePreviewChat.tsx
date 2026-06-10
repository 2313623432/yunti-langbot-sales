import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Mic2, SendHorizontal } from 'lucide-react';
import { toast } from 'sonner';

import { httpClient } from '@/app/infra/http/HttpClient';
import { Message, MessageChainComponent, Plain } from '@/app/infra/entities/message';
import {
  WebSocketClient,
  WebSocketMessage,
} from '@/app/infra/websocket/WebSocketClient';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

interface PipelinePreviewChatProps {
  pipelineId?: string;
  avatarUrl: string;
  agentName: string;
  openingMessage: string;
  voiceEnabled?: boolean;
  hasUnsavedChanges?: boolean;
}

function messagePlainText(message: Message | WebSocketMessage): string {
  return message.message_chain
    .filter((component) => component.type === 'Plain')
    .map((component) => (component as Plain).text || '')
    .join('');
}

export default function PipelinePreviewChat({
  pipelineId,
  avatarUrl,
  agentName,
  openingMessage,
  voiceEnabled = false,
  hasUnsavedChanges = false,
}: PipelinePreviewChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const wsClientRef = useRef<WebSocketClient | null>(null);
  const connectionGenerationRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    });
  }, []);

  const loadMessages = useCallback(async (targetPipelineId: string) => {
    try {
      const response = await httpClient.getWebSocketHistoryMessages(
        targetPipelineId,
        'person',
      );
      setMessages(response.messages || []);
    } catch (error) {
      console.warn('Failed to load preview chat history', error);
      setMessages([]);
    }
  }, []);

  const disconnectCurrentClient = useCallback(() => {
    if (wsClientRef.current) {
      wsClientRef.current.disconnect();
      wsClientRef.current = null;
    }
  }, []);

  const connectWebSocket = useCallback(
    async (targetPipelineId: string, generation: number) => {
      disconnectCurrentClient();
      setIsConnected(false);
      setIsConnecting(true);

      const wsClient = new WebSocketClient(targetPipelineId, 'person');

      wsClient
        .onConnected(() => {
          if (connectionGenerationRef.current !== generation) {
            return;
          }
          setIsConnected(true);
          setIsConnecting(false);
        })
        .onMessage((wsMessage) => {
          if (connectionGenerationRef.current !== generation) {
            return;
          }

          const message: Message = {
            ...wsMessage,
            message_chain: wsMessage.message_chain as MessageChainComponent[],
          };

          setMessages((prevMessages) => {
            const existingIndex = prevMessages.findIndex(
              (item) => item.id === message.id,
            );
            if (existingIndex >= 0) {
              const nextMessages = [...prevMessages];
              nextMessages[existingIndex] = message;
              return nextMessages;
            }
            return [...prevMessages, message];
          });
        })
        .onError((error) => {
          if (connectionGenerationRef.current !== generation) {
            return;
          }
          console.error('Preview chat WebSocket error:', error);
          setIsConnected(false);
          setIsConnecting(false);
          toast.error('预览调试连接失败，请确认后端已启动');
        })
        .onClose(() => {
          if (connectionGenerationRef.current !== generation) {
            return;
          }
          setIsConnected(false);
          setIsConnecting(false);
        });

      try {
        await wsClient.connect();
        if (connectionGenerationRef.current !== generation) {
          wsClient.disconnect();
          return;
        }
        wsClientRef.current = wsClient;
      } catch (error) {
        if (connectionGenerationRef.current !== generation) {
          return;
        }
        console.error('Preview chat WebSocket connection failed:', error);
        setIsConnected(false);
        setIsConnecting(false);
        toast.error('预览调试连接失败，请确认后端已启动');
      }
    },
    [disconnectCurrentClient],
  );

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (!pipelineId) {
      connectionGenerationRef.current += 1;
      disconnectCurrentClient();
      setMessages([]);
      setIsConnected(false);
      setIsConnecting(false);
      return;
    }

    const generation = connectionGenerationRef.current + 1;
    connectionGenerationRef.current = generation;

    setMessages([]);
    void loadMessages(pipelineId);
    void connectWebSocket(pipelineId, generation);

    return () => {
      connectionGenerationRef.current += 1;
      disconnectCurrentClient();
      setIsConnected(false);
      setIsConnecting(false);
    };
  }, [pipelineId, loadMessages, connectWebSocket, disconnectCurrentClient]);

  const sendMessage = async () => {
    const text = inputValue.trim();
    if (!text || !pipelineId) {
      return;
    }
    if (!isConnected || !wsClientRef.current) {
      toast.error('预览调试未连接，请稍后重试');
      return;
    }

    try {
      setIsSending(true);
      wsClientRef.current.sendMessage([{ type: 'Plain', text }], true);
      setInputValue('');
    } catch (error) {
      console.error('Failed to send preview chat message:', error);
      toast.error('发送失败，请重试');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const canSend =
    Boolean(pipelineId) &&
    isConnected &&
    Boolean(inputValue.trim()) &&
    !isSending;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-4 shrink-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <img
            src={avatarUrl}
            alt="Agent头像"
            className="size-11 shrink-0 rounded-full border border-white bg-white object-cover shadow-sm"
          />
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold text-slate-950">
              {agentName || '未命名数字员工'}
            </h3>
            <div className="mt-1 flex items-center gap-2 text-xs">
              <span
                className={cn(
                  'inline-block size-2 rounded-full',
                  isConnected
                    ? 'bg-emerald-500'
                    : isConnecting
                      ? 'bg-amber-400'
                      : 'bg-slate-300',
                )}
              />
              <span className="text-slate-500">
                {!pipelineId
                  ? '请先保存数字员工'
                  : isConnected
                    ? '在线 · 可调试'
                    : isConnecting
                      ? '连接中...'
                      : '未连接'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {hasUnsavedChanges && (
        <div className="mb-3 shrink-0 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
          你有未保存的修改。当前对话基于已保存配置运行，请先点右上角「保存」后再测最新效果。
        </div>
      )}

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="space-y-4">
          <div className="flex gap-3">
            <img
              src={avatarUrl}
              alt="Agent头像"
              className="size-8 shrink-0 rounded-full border border-white bg-white object-cover shadow-sm"
            />
            <div className="max-w-[82%] rounded-lg rounded-tl-sm bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-800">
              {openingMessage.trim() ? (
                openingMessage
              ) : (
                <span className="text-slate-400">开场白会显示在这里</span>
              )}
            </div>
          </div>

          {messages.map((message) => {
            const text = messagePlainText(message);
            if (!text.trim()) {
              return null;
            }

            if (message.role === 'user') {
              return (
                <div key={`${message.id}-${message.timestamp}`} className="flex justify-end">
                  <div className="max-w-[82%] rounded-lg rounded-tr-sm bg-indigo-600 px-4 py-3 text-sm leading-6 text-white">
                    {text}
                  </div>
                </div>
              );
            }

            return (
              <div key={`${message.id}-${message.timestamp}`} className="flex gap-3">
                <img
                  src={avatarUrl}
                  alt="Agent头像"
                  className="size-8 shrink-0 rounded-full border border-white bg-white object-cover shadow-sm"
                />
                <div className="max-w-[82%] rounded-lg rounded-tl-sm bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-800 whitespace-pre-wrap">
                  {text}
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="mt-4 shrink-0 rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
        <div className="flex items-center gap-2 rounded-md bg-slate-50 px-3 py-2.5">
          <Input
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!pipelineId || isSending}
            className="h-8 flex-1 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
            placeholder={
              pipelineId
                ? isConnected
                  ? '在此提问，测试基于配置的回答效果'
                  : isConnecting
                    ? '连接中，请稍候...'
                    : '预览调试未连接，请刷新页面后重试'
                : '请先保存数字员工后再调试'
            }
          />
          <Mic2
            className={cn(
              'size-4 shrink-0',
              voiceEnabled ? 'text-indigo-600' : 'text-muted-foreground',
            )}
          />
          <Button
            type="button"
            size="sm"
            className="h-8 rounded-md px-3"
            disabled={!canSend}
            onClick={() => void sendMessage()}
          >
            {isSending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <>
                <SendHorizontal className="mr-1.5 size-3.5" />
                发送
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
