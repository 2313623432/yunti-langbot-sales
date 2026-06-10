/**
 * WebSocket客户端类
 * 用于管理WebSocket连接和消息处理
 */
export interface WebSocketMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  message_chain: Array<{ type: string; text?: string; target?: string }>;
  timestamp: string;
  is_final?: boolean;
  connection_id?: string;
}

export interface WebSocketResponse {
  type:
    | 'connected'
    | 'response'
    | 'user_message'
    | 'pong'
    | 'broadcast'
    | 'error';
  connection_id?: string;
  pipeline_uuid?: string;
  session_type?: string;
  timestamp?: string;
  data?: WebSocketMessage;
  message?: string;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private connectionId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000; // 3秒重连间隔
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private heartbeatIntervalMs = 30000; // 30秒
  private isConnecting = false; // 防止重复连接
  private connectPromiseResolve: ((connectionId: string) => void) | null = null;
  private connectPromiseReject: ((error: Error) => void) | null = null;
  private connectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private readonly connectTimeoutMs = 15000;

  // 事件回调
  private onConnectedCallback?: (data: WebSocketResponse) => void;
  private onMessageCallback?: (data: WebSocketMessage) => void;
  private onErrorCallback?: (error: Error) => void;
  private onCloseCallback?: () => void;
  private onBroadcastCallback?: (message: string) => void;

  constructor(
    private pipelineId: string,
    private sessionType: 'person' | 'group' = 'person',
    private token?: string,
  ) {}

  private buildWebSocketUrl(): string {
    const path = `/api/v1/pipelines/${this.pipelineId}/ws/connect?session_type=${this.sessionType}`;
    const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

    if (typeof window !== 'undefined') {
      if (apiBase) {
        const base = new URL(apiBase, window.location.origin);
        const protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${base.host}${path}`;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.host}${path}`;
    }

    return path;
  }

  private clearConnectPromise(error?: Error) {
    if (this.connectTimeoutId) {
      clearTimeout(this.connectTimeoutId);
      this.connectTimeoutId = null;
    }

    if (error) {
      this.connectPromiseReject?.(error);
    }

    this.connectPromiseResolve = null;
    this.connectPromiseReject = null;
  }

  private resolveConnect(connectionId: string) {
    if (this.connectTimeoutId) {
      clearTimeout(this.connectTimeoutId);
      this.connectTimeoutId = null;
    }

    this.connectionId = connectionId;
    this.connectPromiseResolve?.(connectionId);
    this.connectPromiseResolve = null;
    this.connectPromiseReject = null;
  }

  /**
   * 连接到WebSocket服务器
   */
  public connect(): Promise<string> {
    return new Promise((resolve, reject) => {
      try {
        // 防止重复连接
        if (
          this.isConnecting ||
          (this.ws && this.ws.readyState === WebSocket.CONNECTING)
        ) {
          console.warn('WebSocket正在连接中，忽略重复连接请求');
          reject(new Error('Connection already in progress'));
          return;
        }

        // 如果已经连接，直接返回
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          console.warn('WebSocket已连接，忽略重复连接请求');
          resolve(this.connectionId || '');
          return;
        }

        this.isConnecting = true;
        this.connectPromiseResolve = resolve;
        this.connectPromiseReject = reject;

        const url = this.buildWebSocketUrl();
        this.ws = new WebSocket(url);

        this.connectTimeoutId = setTimeout(() => {
          if (!this.connectionId) {
            const timeoutError = new Error('WebSocket connection timeout');
            this.isConnecting = false;
            this.onErrorCallback?.(timeoutError);
            this.clearConnectPromise(timeoutError);
            this.ws?.close();
          }
        }, this.connectTimeoutMs);

        // 连接打开
        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          this.isConnecting = false;
          this.startHeartbeat();
        };

        // 接收消息
        this.ws.onmessage = (event) => {
          try {
            const data: WebSocketResponse = JSON.parse(event.data);
            this.handleMessage(data);

            // 第一次连接成功
            if (data.type === 'connected' && data.connection_id) {
              this.resolveConnect(data.connection_id);
            }
          } catch (error) {
            console.error('解析WebSocket消息失败:', error);
            this.onErrorCallback?.(error as Error);
          }
        };

        // 连接关闭
        this.ws.onclose = () => {
          this.isConnecting = false;
          this.stopHeartbeat();
          if (!this.connectionId) {
            this.clearConnectPromise(new Error('WebSocket closed before connected'));
          } else {
            this.clearConnectPromise();
          }
          this.onCloseCallback?.();

          // 自动重连
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
              this.connect().catch(console.error);
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };

        // 连接错误
        this.ws.onerror = (event) => {
          console.error('WebSocket错误:', event);
          this.isConnecting = false;
          const error = new Error('WebSocket连接失败');
          this.onErrorCallback?.(error);
          this.clearConnectPromise(error);
        };
      } catch (error) {
        this.isConnecting = false;
        this.clearConnectPromise(error as Error);
        reject(error);
      }
    });
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(data: WebSocketResponse) {
    switch (data.type) {
      case 'connected':
        this.onConnectedCallback?.(data);
        break;

      case 'response':
        // 检查 session_type 是否匹配 - 如果消息没有 session_type 或者不匹配当前session，都忽略
        if (!data.session_type || data.session_type !== this.sessionType) {
          // 忽略不匹配的 session_type 消息
          console.debug(
            `忽略不匹配的消息: 当前session=${this.sessionType}, 消息session=${data.session_type}`,
          );
          break;
        }
        if (data.data) {
          this.onMessageCallback?.(data.data);
        }
        break;

      case 'user_message':
        // 检查 session_type 是否匹配 - 如果消息没有 session_type 或者不匹配当前session，都忽略
        if (!data.session_type || data.session_type !== this.sessionType) {
          // 忽略不匹配的 session_type 消息
          console.debug(
            `忽略不匹配的用户消息: 当前session=${this.sessionType}, 消息session=${data.session_type}`,
          );
          break;
        }
        // 用户消息广播（包括自己发送的消息）
        if (data.data) {
          this.onMessageCallback?.(data.data);
        }
        break;

      case 'pong':
        // 心跳响应
        break;

      case 'broadcast':
        if (data.message) {
          this.onBroadcastCallback?.(data.message);
        }
        break;

      case 'error':
        const error = new Error(data.message || '未知错误');
        this.onErrorCallback?.(error);
        break;

      default:
        console.warn('未知消息类型:', data);
    }
  }

  /**
   * 发送消息
   */
  public sendMessage(
    messageChain: Array<{ type: string; text?: string; target?: string }>,
    stream: boolean = true,
  ) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket未连接');
    }

    const message = {
      type: 'message',
      message: messageChain,
      stream: stream,
    };

    this.ws.send(JSON.stringify(message));
  }

  /**
   * 发送心跳
   */
  private sendHeartbeat() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({ type: 'ping' }));
  }

  /**
   * 启动心跳
   */
  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatIntervalMs);
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * 断开连接
   */
  public disconnect() {
    // 停止自动重连
    this.reconnectAttempts = this.maxReconnectAttempts;
    this.clearConnectPromise(new Error('WebSocket disconnected'));

    if (this.ws) {
      this.stopHeartbeat();

      // 发送断开消息
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'disconnect' }));
      }

      this.ws.close();
      this.ws = null;
      this.connectionId = null;
      this.isConnecting = false;
    }
  }

  /**
   * 获取连接ID
   */
  public getConnectionId(): string | null {
    return this.connectionId;
  }

  /**
   * 获取连接状态
   */
  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  // ===== 事件回调设置 =====

  public onConnected(callback: (data: WebSocketResponse) => void) {
    this.onConnectedCallback = callback;
    return this;
  }

  public onMessage(callback: (data: WebSocketMessage) => void) {
    this.onMessageCallback = callback;
    return this;
  }

  public onError(callback: (error: Error) => void) {
    this.onErrorCallback = callback;
    return this;
  }

  public onClose(callback: () => void) {
    this.onCloseCallback = callback;
    return this;
  }

  public onBroadcast(callback: (message: string) => void) {
    this.onBroadcastCallback = callback;
    return this;
  }
}
