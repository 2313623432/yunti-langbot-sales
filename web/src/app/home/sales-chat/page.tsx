import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BriefcaseBusiness,
  CalendarClock,
  Database,
  Edit3,
  Eye,
  Handshake,
  History,
  Loader2,
  MessageSquare,
  PackagePlus,
  RefreshCw,
  Search,
  Sparkles,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import {
  SalesCustomerMemory,
  SalesHandoff,
  SalesOverview,
  SalesProduct,
  SalesOutreachPlan,
} from '@/app/infra/entities/api';
import { httpClient, initializeUserInfo, userInfo } from '@/app/infra/http';
import { MessageContentRenderer } from '@/app/home/monitoring/components/MessageContentRenderer';
import { cn } from '@/lib/utils';

type MainView = 'conversation' | 'customers' | 'workbench';
type RightPanel = 'customer' | 'talk' | 'material' | 'history';

type MonitoringSession = {
  session_id: string;
  bot_id: string;
  bot_name: string;
  pipeline_id: string;
  pipeline_name: string;
  message_count: number;
  start_time: string;
  last_activity: string;
  is_active?: boolean;
  platform?: string | null;
  user_id?: string | null;
  user_name?: string | null;
};

type MonitoringMessage = {
  id: string;
  timestamp: string;
  bot_id: string;
  bot_name: string;
  pipeline_id: string;
  pipeline_name: string;
  message_content: string;
  session_id: string;
  status: string;
  level: string;
  platform: string | null;
  user_id: string | null;
  user_name: string | null;
  runner_name: string | null;
  variables: string | null;
  role: string | null;
};

type ConversationRow = {
  sessionId: string;
  name: string;
  preview: string;
  time: string;
  platform: string;
  messageCount: number;
  stage: string;
  handoff?: SalesHandoff;
  memory?: SalesCustomerMemory;
  session?: MonitoringSession;
};

type CustomerProfileDraft = {
  customer_name: string;
  stage: string;
  phone: string;
  wechat: string;
  email: string;
  company: string;
  industry: string;
  title: string;
  location: string;
  budget: string;
  child_grade: string;
  needs: string;
  summary: string;
};

type MessageContentComponent = {
  type?: string;
  text?: string;
  display?: string;
  target?: string | number;
  name?: string;
  length?: number;
  origin?: MessageContentComponent[];
};

const profileFields: Array<{
  key: keyof CustomerProfileDraft;
  label: string;
}> = [
  { key: 'phone', label: '电话/手机号' },
  { key: 'wechat', label: '微信号' },
  { key: 'email', label: '邮箱' },
  { key: 'company', label: '公司名称' },
  { key: 'industry', label: '行业类别' },
  { key: 'title', label: '职位' },
  { key: 'location', label: '所在地' },
  { key: 'budget', label: '客单价/预算' },
  { key: 'child_grade', label: '孩子年级' },
  { key: 'needs', label: '关注需求' },
];

const stageLabels: Record<string, string> = {
  new: '新客户',
  consideration: '考虑中',
  high_intent: '高意向',
  handoff: '已转人工',
};

const intentLabels: Record<string, string> = {
  handoff: '转人工',
  price: '价格咨询',
  purchase: '购买意向',
  comparison: '对比咨询',
  objection: '异议处理',
  product_interest: '产品兴趣',
  general: '普通咨询',
};

function errorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'msg' in error) {
    return String((error as { msg?: string }).msg);
  }
  if (error instanceof Error) return error.message;
  return '请求失败';
}

function formatDate(value?: string | null): string {
  if (!value) return '暂无';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function stageLabel(stage?: string): string {
  return stageLabels[stage || ''] || stage || '新客户';
}

function intentLabel(intent?: string): string {
  return intentLabels[intent || ''] || intent || '未识别';
}

function platformLabel(platform?: string | null): string {
  if (!platform) return '未知渠道';
  if (platform.includes('LauncherTypes.PERSON')) return '私聊';
  if (platform.includes('LauncherTypes.GROUP')) return '群聊';
  if (platform.includes('Wecom') || platform.includes('wecom'))
    return '企业微信';
  if (platform === 'person') return '私聊';
  if (platform === 'group') return '群聊';
  return platform;
}

function isTechnicalIdentifier(value?: string | null): boolean {
  const text = String(value || '').trim();
  if (!text) return true;
  return (
    text.includes('LauncherTypes.') ||
    /^(on|om|ou|oc|of)_[A-Za-z0-9_-]{12,}$/.test(text) ||
    /^[A-Za-z]+Types\.[A-Z_]+_/.test(text)
  );
}

function displayCustomerName(
  memory?: SalesCustomerMemory,
  session?: MonitoringSession,
  handoff?: SalesHandoff,
): string {
  const candidates = [
    memory?.customer_name,
    session?.user_name,
    handoff?.user_id,
    session?.user_id,
  ];
  const readable = candidates.find((item) => !isTechnicalIdentifier(item));
  if (readable) return readable;
  const source = platformLabel(
    session?.platform || memory?.platform || handoff?.platform,
  );
  if (source === '私聊' || source === '群聊') return `${source}客户`;
  return '客户';
}

function compactIdentifier(value?: string | null): string {
  const text = String(value || '').trim();
  if (!text) return '暂无ID';
  return text.length > 28 ? `${text.slice(0, 12)}...${text.slice(-8)}` : text;
}

function messageContentText(content?: string | null): string {
  if (!content) return '';
  try {
    const parsed = JSON.parse(content) as unknown;
    if (!Array.isArray(parsed)) return content;
    return parsed
      .map((component) => {
        if (!component || typeof component !== 'object') return '';
        const item = component as MessageContentComponent;
        if (item.type === 'Plain') return item.text || '';
        if (item.type === 'At') return `@${item.display || item.target || ''}`;
        if (item.type === 'AtAll') return '@All';
        if (item.type === 'Image') return '[图片]';
        if (item.type === 'File')
          return `[文件${item.name ? `: ${item.name}` : ''}]`;
        if (item.type === 'Voice')
          return `[语音${item.length ? ` ${item.length}s` : ''}]`;
        if (item.type === 'Quote')
          return messageContentText(JSON.stringify(item.origin || []));
        if (item.type === 'Source') return '';
        return item.type ? `[${item.type}]` : '';
      })
      .join('')
      .trim();
  } catch {
    return content;
  }
}

function conversationAccountLabel(conversation: ConversationRow): string {
  return (
    conversation.session?.bot_name ||
    conversation.handoff?.assigned_to ||
    '未分配账号'
  );
}

function conversationMessageTypeLabel(conversation: ConversationRow): string {
  const targetType =
    conversation.handoff?.target_type || conversation.session?.platform;
  if (targetType === 'group') return '群聊';
  if (targetType === 'person') return '私聊';
  return conversation.platform;
}

function conversationReplyModeLabel(conversation: ConversationRow): string {
  if (conversation.handoff) return '待人工';
  return 'AI自动';
}

function uniqueLabels(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function productIdentity(product: SalesProduct): string {
  return product.uuid || product.name;
}

function compactList(items: string[], fallback = '暂无'): string {
  return items.filter(Boolean).join('、') || fallback;
}

function getProfileValue(
  memory: SalesCustomerMemory | undefined,
  key: keyof CustomerProfileDraft,
): string {
  const aliases: Record<keyof CustomerProfileDraft, string[]> = {
    customer_name: ['customer_name', 'name', '客户名称', '姓名'],
    stage: ['stage', '客户阶段'],
    phone: [
      'phone',
      'mobile',
      'phone_number',
      'mobile_phone',
      'tel',
      'telephone',
      '手机号',
      '手机',
      '电话',
      '电话号码',
    ],
    wechat: ['wechat', 'wechat_id', 'weixin', '微信', '微信号'],
    email: ['email', 'mail', '邮箱', '电子邮箱'],
    company: [
      'company',
      'company_name',
      'organization',
      '公司',
      '公司名称',
      '单位',
    ],
    industry: ['industry', 'industry_category', '行业', '行业类别'],
    title: ['title', 'job_title', 'position', '职位', '职务'],
    location: [
      'location',
      'city',
      'region',
      'address',
      '所在地',
      '城市',
      '地区',
      '地址',
    ],
    budget: ['budget', 'price', 'expected_price', '客单价', '预算', '预算范围'],
    child_grade: ['child_grade', 'grade', 'target_grade', '孩子年级', '年级'],
    needs: ['needs', 'demand', 'pain_point', '关注需求', '需求', '痛点'],
    summary: ['summary', '客户摘要', '摘要'],
  };
  const profile = memory?.profile;
  if (!profile || typeof profile !== 'object') return '';
  for (const alias of aliases[key] || [key]) {
    const value = profile[alias];
    if (typeof value === 'string' && value.trim()) return value;
    if (typeof value === 'number') return String(value);
  }
  return '';
}

function makeProfileDraft(
  memory: SalesCustomerMemory | undefined,
): CustomerProfileDraft {
  return {
    customer_name: isTechnicalIdentifier(memory?.customer_name)
      ? ''
      : memory?.customer_name || '',
    stage: memory?.stage || 'new',
    phone: getProfileValue(memory, 'phone'),
    wechat: getProfileValue(memory, 'wechat'),
    email: getProfileValue(memory, 'email'),
    company: getProfileValue(memory, 'company'),
    industry: getProfileValue(memory, 'industry'),
    title: getProfileValue(memory, 'title'),
    location: getProfileValue(memory, 'location'),
    budget: getProfileValue(memory, 'budget'),
    child_grade: getProfileValue(memory, 'child_grade'),
    needs: getProfileValue(memory, 'needs'),
    summary: memory?.summary || '',
  };
}

function Avatar({ name, active }: { name: string; active?: boolean }) {
  const initial = name.trim().slice(0, 1) || '客';
  return (
    <div className="relative flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-slate-700 to-slate-400 text-base font-semibold text-white shadow-sm">
      {initial}
      {active && (
        <span className="absolute -bottom-0.5 -right-0.5 size-3 rounded-[3px] border-2 border-white bg-[#45cf72]" />
      )}
    </div>
  );
}

function AppRail({
  activeView,
  onViewChange,
}: {
  activeView: MainView;
  onViewChange: (view: MainView) => void;
}) {
  const items: Array<{
    label: string;
    icon: typeof MessageSquare;
    view: MainView;
  }> = [
    { label: '对话', icon: MessageSquare, view: 'conversation' },
    { label: '客户', icon: Users, view: 'customers' },
    { label: '工作台', icon: BriefcaseBusiness, view: 'workbench' },
  ];

  return (
    <nav className="border-r border-[#dde0e6] bg-[#eef0f3] py-2">
      <div className="flex flex-col items-center gap-2">
        {items.map((item) => (
          <button
            key={item.view}
            type="button"
            onClick={() => onViewChange(item.view)}
            className={cn(
              'flex w-12 flex-col items-center gap-1 rounded-xl py-2 text-xs transition',
              activeView === item.view
                ? 'bg-[#e3e4ff] text-[#5a55ff]'
                : 'text-[#8e96a6] hover:bg-white/70',
            )}
          >
            <item.icon className="size-5" />
            {item.label}
          </button>
        ))}
      </div>
    </nav>
  );
}

function Shell({
  activeView,
  onViewChange,
  children,
}: {
  activeView: MainView;
  onViewChange: (view: MainView) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="h-full min-h-0 overflow-hidden bg-[#eef0f3] text-[#1f2a44]">
      <div className="h-full min-h-0 overflow-x-auto">
        <div className="h-full min-w-[1320px] rounded-lg border border-[#dde0e6] bg-white">
          <div className="grid h-full min-h-0 grid-cols-[68px_minmax(0,1fr)]">
            <AppRail activeView={activeView} onViewChange={onViewChange} />
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex h-full min-h-[220px] flex-col items-center justify-center px-8 text-center text-[#7b8497]">
      <MessageSquare className="mb-3 size-10 text-[#b6bdca]" />
      <div className="text-base font-medium text-[#34415c]">{title}</div>
      <div className="mt-2 max-w-md text-sm leading-6">{description}</div>
    </div>
  );
}

function buildConversations(
  sessions: MonitoringSession[],
  memories: SalesCustomerMemory[],
  handoffs: SalesHandoff[],
): ConversationRow[] {
  const sessionMap = new Map(
    sessions.map((session) => [session.session_id, session]),
  );
  const memoryMap = new Map(
    memories.map((memory) => [memory.session_id, memory]),
  );
  const handoffMap = new Map(
    handoffs.map((handoff) => [handoff.session_id, handoff]),
  );
  const ids = new Set<string>([
    ...sessions.map((session) => session.session_id),
    ...memories.map((memory) => memory.session_id),
    ...handoffs.map((handoff) => handoff.session_id),
  ]);

  return [...ids]
    .map((sessionId) => {
      const session = sessionMap.get(sessionId);
      const memory = memoryMap.get(sessionId);
      const handoff = handoffMap.get(sessionId);
      const name = displayCustomerName(memory, session, handoff);
      const preview =
        messageContentText(handoff?.last_message) ||
        memory?.summary ||
        (session ? `${session.message_count} 条真实消息` : '暂无消息摘要');
      const time = formatDate(
        handoff?.updated_at || memory?.last_seen_at || session?.last_activity,
      );
      return {
        sessionId,
        name,
        preview,
        time,
        platform: platformLabel(
          session?.platform || memory?.platform || handoff?.platform,
        ),
        messageCount: session?.message_count || 0,
        stage: memory?.stage || (handoff ? 'handoff' : 'new'),
        handoff,
        memory,
        session,
      };
    })
    .sort((a, b) => {
      const aTime =
        new Date(
          a.handoff?.updated_at ||
            a.memory?.last_seen_at ||
            a.session?.last_activity ||
            0,
        ).getTime() || 0;
      const bTime =
        new Date(
          b.handoff?.updated_at ||
            b.memory?.last_seen_at ||
            b.session?.last_activity ||
            0,
        ).getTime() || 0;
      return bTime - aTime;
    });
}

function ConversationFilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="min-w-0 text-sm text-[#34415c]">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-md border border-transparent bg-white px-2 text-[#34415c] outline-none hover:border-[#dde2ec] focus:border-[#5f58ff]"
      >
        <option value="all">{label}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function ConversationList({
  conversations,
  selectedSessionId,
  query,
  accountFilter,
  messageTypeFilter,
  replyModeFilter,
  accountOptions,
  messageTypeOptions,
  replyModeOptions,
  loading,
  onQuery,
  onAccountFilter,
  onMessageTypeFilter,
  onReplyModeFilter,
  onSelect,
}: {
  conversations: ConversationRow[];
  selectedSessionId: string;
  query: string;
  accountFilter: string;
  messageTypeFilter: string;
  replyModeFilter: string;
  accountOptions: string[];
  messageTypeOptions: string[];
  replyModeOptions: string[];
  loading: boolean;
  onQuery: (value: string) => void;
  onAccountFilter: (value: string) => void;
  onMessageTypeFilter: (value: string) => void;
  onReplyModeFilter: (value: string) => void;
  onSelect: (sessionId: string) => void;
}) {
  const [quickPanel, setQuickPanel] = useState<'add' | 'contacts' | null>(null);
  const selectedConversation = conversations.find(
    (conversation) => conversation.sessionId === selectedSessionId,
  );
  const filtered = conversations.filter((conversation) => {
    const account = conversationAccountLabel(conversation);
    const messageType = conversationMessageTypeLabel(conversation);
    const replyMode = conversationReplyModeLabel(conversation);
    const text =
      `${conversation.name}${conversation.preview}${conversation.platform}${account}${messageType}${replyMode}`.toLowerCase();
    const matchesQuery =
      !query.trim() || text.includes(query.trim().toLowerCase());
    const matchesAccount = accountFilter === 'all' || accountFilter === account;
    const matchesMessageType =
      messageTypeFilter === 'all' || messageTypeFilter === messageType;
    const matchesReplyMode =
      replyModeFilter === 'all' || replyModeFilter === replyMode;
    return (
      matchesQuery && matchesAccount && matchesMessageType && matchesReplyMode
    );
  });

  return (
    <aside className="relative flex min-h-0 flex-col border-r border-[#dde0e6] bg-white">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-[#eef0f4] px-6">
        <h1 className="text-2xl font-semibold text-[#111827]">对话</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            title="加好友"
            onClick={() =>
              setQuickPanel((panel) => (panel === 'add' ? null : 'add'))
            }
            className={cn(
              'flex size-10 items-center justify-center rounded-xl border border-[#dde2ec] text-[#8d95a6] transition hover:border-[#cfd5e2] hover:text-[#5f58ff]',
              quickPanel === 'add' &&
                'border-[#c9c6ff] bg-[#f1f0ff] text-[#5f58ff]',
            )}
          >
            <UserPlus className="size-5" />
          </button>
          <button
            type="button"
            title="通讯录"
            onClick={() =>
              setQuickPanel((panel) =>
                panel === 'contacts' ? null : 'contacts',
              )
            }
            className={cn(
              'flex size-10 items-center justify-center rounded-xl border border-[#dde2ec] text-[#8d95a6] transition hover:border-[#cfd5e2] hover:text-[#5f58ff]',
              quickPanel === 'contacts' &&
                'border-[#c9c6ff] bg-[#f1f0ff] text-[#5f58ff]',
            )}
          >
            <Users className="size-5" />
          </button>
          {loading && (
            <Loader2 className="size-5 animate-spin text-[#7b8497]" />
          )}
        </div>
      </div>
      {quickPanel && (
        <div className="absolute right-5 top-14 z-20 w-[292px] rounded-xl border border-[#e2e6ef] bg-white p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <div className="font-medium text-[#1f2a44]">
              {quickPanel === 'add' ? '加好友' : '通讯录'}
            </div>
            <button
              type="button"
              onClick={() => setQuickPanel(null)}
              className="text-[#8b93a5]"
            >
              <X className="size-4" />
            </button>
          </div>

          {quickPanel === 'add' && (
            <div className="space-y-3 text-sm text-[#687086]">
              <div className="rounded-lg bg-[#f7f8fb] p-3 leading-6">
                当前项目没有开放独立加好友接口。可从真实会话里选择客户，并通过对应平台完成添加或接入。
              </div>
              <label className="grid gap-1">
                当前客户
                <input
                  readOnly
                  value={selectedConversation?.name || '请先选择会话'}
                  className="h-9 rounded-md border border-[#e2e6ef] bg-[#fbfcff] px-3 text-[#34415c]"
                />
              </label>
              <label className="grid gap-1">
                客户标识
                <input
                  readOnly
                  value={
                    selectedConversation?.session?.user_id ||
                    selectedConversation?.handoff?.user_id ||
                    selectedConversation?.sessionId ||
                    ''
                  }
                  placeholder="暂无"
                  className="h-9 rounded-md border border-[#e2e6ef] bg-[#fbfcff] px-3 text-[#34415c]"
                />
              </label>
              <button
                type="button"
                onClick={() => {
                  if (!selectedConversation) {
                    toast.info('请先选择一个会话');
                    return;
                  }
                  onSelect(selectedConversation.sessionId);
                  setQuickPanel(null);
                }}
                className="w-full rounded-lg bg-[#5f58ff] px-3 py-2 text-white"
              >
                查看当前会话
              </button>
            </div>
          )}

          {quickPanel === 'contacts' && (
            <div className="max-h-[320px] overflow-auto">
              {conversations.slice(0, 12).map((conversation) => (
                <button
                  key={conversation.sessionId}
                  type="button"
                  onClick={() => {
                    onSelect(conversation.sessionId);
                    setQuickPanel(null);
                  }}
                  className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-[#f7f8fb]"
                >
                  <Avatar
                    name={conversation.name}
                    active={conversation.session?.is_active}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-[#34415c]">
                      {conversation.name}
                    </div>
                    <div className="truncate text-xs text-[#7c8496]">
                      {conversationAccountLabel(conversation)} ·{' '}
                      {conversationMessageTypeLabel(conversation)}
                    </div>
                  </div>
                </button>
              ))}
              {!conversations.length && (
                <div className="rounded-lg bg-[#f7f8fb] p-4 text-center text-sm leading-6 text-[#7c8496]">
                  暂无真实通讯录数据，产生监控会话或客户记忆后会自动出现在这里。
                </div>
              )}
            </div>
          )}
        </div>
      )}
      <div className="space-y-4 border-b border-[#eef0f4] px-5 py-4">
        <label className="flex h-11 items-center gap-2 rounded-lg border border-[#dde2ec] px-3 text-[#97a0b3]">
          <Search className="size-5" />
          <input
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            className="w-full bg-transparent text-sm outline-none"
            placeholder="搜索客户/会话/平台"
          />
        </label>
        <div className="grid grid-cols-3 gap-2">
          <ConversationFilterSelect
            label="所属账号"
            value={accountFilter}
            options={accountOptions}
            onChange={onAccountFilter}
          />
          <ConversationFilterSelect
            label="消息类型"
            value={messageTypeFilter}
            options={messageTypeOptions}
            onChange={onMessageTypeFilter}
          />
          <ConversationFilterSelect
            label="回复方式"
            value={replyModeFilter}
            options={replyModeOptions}
            onChange={onReplyModeFilter}
          />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-3 py-3">
        {filtered.map((conversation) => (
          <button
            key={conversation.sessionId}
            type="button"
            onClick={() => onSelect(conversation.sessionId)}
            className={cn(
              'mb-2 flex w-full gap-3 rounded-xl px-3 py-3 text-left transition',
              selectedSessionId === conversation.sessionId
                ? 'bg-[#eef0f7]'
                : 'hover:bg-[#f7f8fb]',
            )}
          >
            <Avatar
              name={conversation.name}
              active={conversation.session?.is_active}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <div className="truncate font-medium text-[#34415c]">
                  {conversation.name}
                </div>
                <div className="shrink-0 text-xs text-[#7c8496]">
                  {conversation.time}
                </div>
              </div>
              <div className="mt-1 line-clamp-2 text-sm leading-5 text-[#687086]">
                {conversation.preview}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span className="rounded bg-[#eff2ff] px-2 py-0.5 text-xs text-[#5f58ff]">
                  {conversation.platform}
                </span>
                <span className="rounded bg-[#f2f5f8] px-2 py-0.5 text-xs text-[#697287]">
                  {stageLabel(conversation.stage)}
                </span>
                {conversation.handoff && (
                  <span className="rounded bg-[#fff1f1] px-2 py-0.5 text-xs text-[#d44a4a]">
                    待人工
                  </span>
                )}
              </div>
            </div>
          </button>
        ))}
        {!filtered.length && (
          <EmptyState
            title="暂无真实会话"
            description="当机器人产生监控会话、销售记忆或人工接入记录后，会自动出现在这里。"
          />
        )}
      </div>
    </aside>
  );
}

function ChatCenter({
  conversation,
  messages,
  loading,
  draft,
  sending,
  onDraft,
  onSend,
  onRefresh,
  onOpenHandoff,
}: {
  conversation?: ConversationRow;
  messages: MonitoringMessage[];
  loading: boolean;
  draft: string;
  sending: boolean;
  onDraft: (value: string) => void;
  onSend: () => void;
  onRefresh: () => void;
  onOpenHandoff: () => void;
}) {
  return (
    <main className="flex min-h-0 flex-col bg-[#eef0f6]">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-[#dde0e6] bg-white px-6">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h2 className="truncate text-2xl font-semibold text-[#1f2a44]">
              {conversation?.name || '选择一个会话'}
            </h2>
            {conversation && (
              <span className="text-base text-[#687086]">
                来源-{conversation.platform}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onRefresh}
            className="flex size-10 items-center justify-center rounded-lg border border-[#dde2ec] text-[#697287]"
          >
            <RefreshCw className="size-5" />
          </button>
          <button
            type="button"
            onClick={onOpenHandoff}
            disabled={!conversation}
            className="rounded-lg border border-[#5f58ff] px-4 py-2 text-[#5f58ff] disabled:opacity-50"
          >
            接入人工
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-10 py-8">
        {!conversation ? (
          <EmptyState
            title="请选择会话"
            description="左侧会话来自真实监控记录和销售接入队列。"
          />
        ) : loading ? (
          <div className="flex h-full items-center justify-center text-[#7b8497]">
            <Loader2 className="mr-2 size-5 animate-spin" />
            加载真实消息中
          </div>
        ) : messages.length ? (
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((message) => {
              const isAgent = message.role === 'assistant';
              return (
                <div
                  key={message.id}
                  className={cn('flex gap-3', isAgent && 'justify-end')}
                >
                  {!isAgent && (
                    <Avatar name={message.user_name || conversation.name} />
                  )}
                  <div className={cn('max-w-[72%]', isAgent && 'text-right')}>
                    <div className="mb-1 text-sm text-[#6b7280]">
                      {isAgent
                        ? message.bot_name
                        : message.user_name || conversation.name}
                      <span className="ml-2">
                        {formatDate(message.timestamp)}
                      </span>
                    </div>
                    <div
                      className={cn(
                        'whitespace-pre-wrap rounded-2xl px-5 py-4 text-left text-base leading-7 shadow-sm',
                        isAgent
                          ? 'bg-[#5f58ff] text-white'
                          : 'bg-white text-[#34415c]',
                      )}
                    >
                      <MessageContentRenderer
                        content={message.message_content}
                        maxLines={0}
                      />
                    </div>
                  </div>
                  {isAgent && <Avatar name={message.bot_name || 'AI'} />}
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="暂无消息记录"
            description="该会话已存在于销售链路中，但监控消息表里还没有可展示的消息。"
          />
        )}
      </div>

      <div className="shrink-0 border-t border-[#dde0e6] bg-white px-6 py-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm text-[#7c8496]">
            人工回复会通过真实机器人适配器发送
          </div>
          <div className="text-sm text-[#7c8496]">{draft.length}/600</div>
        </div>
        <div className="flex gap-3">
          <textarea
            value={draft}
            onChange={(event) => onDraft(event.target.value.slice(0, 600))}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                onSend();
              }
            }}
            disabled={!conversation || sending}
            className="min-h-[96px] flex-1 resize-none rounded-xl border border-[#e2e6ef] bg-[#f5f7fb] px-4 py-3 text-base outline-none focus:border-[#5f58ff] disabled:opacity-60"
            placeholder="使用 Enter 发送消息，使用 Shift + Enter 换行"
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!conversation || !draft.trim() || sending}
            className="self-end rounded-lg bg-[#5f58ff] px-5 py-3 text-white disabled:opacity-50"
          >
            {sending ? <Loader2 className="size-5 animate-spin" /> : '发送'}
          </button>
        </div>
      </div>
    </main>
  );
}

function RightPanelContent({
  activePanel,
  conversation,
  products,
  outreachPlans,
  memoryDraft,
  savingMemory,
  onPanel,
  onDraft,
  onSaveMemory,
  onClose,
}: {
  activePanel: RightPanel;
  conversation?: ConversationRow;
  products: SalesProduct[];
  outreachPlans: SalesOutreachPlan[];
  memoryDraft: CustomerProfileDraft;
  savingMemory: boolean;
  onPanel: (panel: RightPanel) => void;
  onDraft: (draft: CustomerProfileDraft) => void;
  onSaveMemory: () => void;
  onClose: () => void;
}) {
  const intentHistory = conversation?.memory?.intents || [];
  const enabledProducts = useMemo(
    () => products.filter((product) => product.enabled),
    [products],
  );
  const [selectedProductKey, setSelectedProductKey] = useState('');
  const [pitching, setPitching] = useState(false);
  const [pitchResult, setPitchResult] = useState<{
    tone: string;
    message: string;
    next_action: string;
  } | null>(null);
  const selectedProduct =
    enabledProducts.find(
      (product) => productIdentity(product) === selectedProductKey,
    ) || enabledProducts[0];

  useEffect(() => {
    if (!enabledProducts.length) {
      setSelectedProductKey('');
      return;
    }
    if (
      !selectedProductKey ||
      !enabledProducts.some(
        (product) => productIdentity(product) === selectedProductKey,
      )
    ) {
      setSelectedProductKey(productIdentity(enabledProducts[0]));
    }
  }, [enabledProducts, selectedProductKey]);

  const generatePitch = async () => {
    if (!selectedProduct) {
      toast.error('暂无可用产品');
      return;
    }
    setPitching(true);
    try {
      const response = await httpClient.generateSalesPitch({
        message: conversation?.preview || '',
        product_uuid: selectedProduct.uuid,
        customer_profile: conversation?.memory?.summary || '',
        intent: conversation?.memory?.last_intent || '',
      });
      setPitchResult(response.pitch);
      toast.success('已生成销售话术');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPitching(false);
    }
  };

  return (
    <aside className="flex min-h-0 border-l border-[#dde0e6] bg-white">
      <div className="min-w-0 flex-1 overflow-auto">
        <div className="flex h-16 items-center justify-between border-b border-[#eef0f4] px-6">
          <h2 className="text-xl font-semibold text-[#1f2a44]">
            {activePanel === 'customer' && '客户信息'}
            {activePanel === 'talk' && '话术库'}
            {activePanel === 'material' && '素材库'}
            {activePanel === 'history' && '历史记录'}
          </h2>
          <button type="button" onClick={onClose} className="text-[#8b93a5]">
            <X className="size-5" />
          </button>
        </div>

        {activePanel === 'customer' && (
          <div className="space-y-5 p-6">
            {!conversation?.memory && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
                该会话还没有销售客户记忆。可直接补充并保存，系统会基于当前真实会话创建客户资料。
              </div>
            )}
            <div className="flex items-center gap-3">
              <Avatar
                name={conversation?.name || memoryDraft.customer_name || '客户'}
                active
              />
              <div className="min-w-0">
                <input
                  value={memoryDraft.customer_name}
                  onChange={(event) =>
                    onDraft({
                      ...memoryDraft,
                      customer_name: event.target.value,
                    })
                  }
                  className="w-full rounded-md border border-transparent px-2 py-1 text-xl font-semibold outline-none hover:border-[#e2e6ef] focus:border-[#5f58ff]"
                  placeholder={conversation?.name || '客户名称'}
                  disabled={!conversation}
                />
                <div className="mt-1 text-sm text-[#6b7280]">
                  {conversation
                    ? `${conversation.platform} · ${compactIdentifier(
                        conversation.session?.user_id ||
                          conversation.handoff?.user_id ||
                          conversation.sessionId,
                      )}`
                    : '暂无会话'}
                </div>
              </div>
            </div>

            <label className="grid gap-2 text-sm text-[#6b7280]">
              客户阶段
              <select
                value={memoryDraft.stage}
                onChange={(event) =>
                  onDraft({ ...memoryDraft, stage: event.target.value })
                }
                disabled={!conversation}
                className="h-10 rounded-lg border border-[#e2e6ef] bg-white px-3 text-[#34415c] outline-none focus:border-[#5f58ff]"
              >
                {Object.entries(stageLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid gap-3">
              {profileFields.map((field) => (
                <label
                  key={field.key}
                  className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3 text-sm"
                >
                  <span className="text-[#7c8496]">{field.label}</span>
                  <input
                    value={String(memoryDraft[field.key] || '')}
                    onChange={(event) =>
                      onDraft({
                        ...memoryDraft,
                        [field.key]: event.target.value,
                      })
                    }
                    disabled={!conversation}
                    className="h-9 rounded-md border border-[#e2e6ef] px-3 text-[#34415c] outline-none focus:border-[#5f58ff] disabled:bg-[#f7f8fb]"
                    placeholder="暂无"
                  />
                </label>
              ))}
            </div>

            <label className="grid gap-2 text-sm text-[#6b7280]">
              客户摘要
              <textarea
                value={memoryDraft.summary}
                onChange={(event) =>
                  onDraft({ ...memoryDraft, summary: event.target.value })
                }
                disabled={!conversation}
                className="min-h-28 resize-none rounded-lg border border-[#e2e6ef] px-3 py-2 text-[#34415c] outline-none focus:border-[#5f58ff] disabled:bg-[#f7f8fb]"
                placeholder="暂无摘要"
              />
            </label>

            <button
              type="button"
              onClick={onSaveMemory}
              disabled={!conversation || savingMemory}
              className="inline-flex items-center gap-2 rounded-lg bg-[#5f58ff] px-4 py-2 text-white disabled:opacity-50"
            >
              {savingMemory ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Edit3 className="size-4" />
              )}
              保存客户信息
            </button>
          </div>
        )}

        {activePanel === 'talk' && (
          <div className="space-y-4 p-6">
            <div className="grid gap-2 text-sm text-[#6b7280]">
              选择产品
              <select
                value={selectedProductKey}
                onChange={(event) => {
                  setSelectedProductKey(event.target.value);
                  setPitchResult(null);
                }}
                disabled={!enabledProducts.length}
                className="h-10 rounded-lg border border-[#e2e6ef] bg-white px-3 text-[#34415c] outline-none focus:border-[#5f58ff] disabled:bg-[#f7f8fb]"
              >
                {enabledProducts.map((product) => (
                  <option
                    key={productIdentity(product)}
                    value={productIdentity(product)}
                  >
                    {product.name}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={() => void generatePitch()}
              disabled={!enabledProducts.length || pitching}
              className="inline-flex items-center gap-2 rounded-lg bg-[#5f58ff] px-4 py-2 text-white disabled:opacity-50"
            >
              {pitching ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              基于当前会话生成话术
            </button>

            {pitchResult && (
              <div className="rounded-xl border border-[#e2e6ef] bg-[#fbfcff] p-4">
                <div className="text-sm text-[#7c8496]">
                  语气：{pitchResult.tone || 'consultative'}
                </div>
                <div className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#34415c]">
                  {pitchResult.message}
                </div>
                <div className="mt-3 rounded-lg bg-[#eff2ff] px-3 py-2 text-sm text-[#5f58ff]">
                  下一步：{pitchResult.next_action || '继续跟进客户'}
                </div>
              </div>
            )}

            <div className="rounded-lg border border-[#e2e6ef]">
              <div className="border-b border-[#eef0f4] px-4 py-3 font-medium">
                产品话术来源
              </div>
              <div className="max-h-[420px] overflow-auto p-3">
                {enabledProducts.map((product) => (
                  <div
                    key={productIdentity(product)}
                    className="mb-3 rounded-lg border border-[#eef0f4] p-3 last:mb-0"
                  >
                    <div className="font-medium text-[#34415c]">
                      {product.name}
                    </div>
                    <div className="mt-1 text-sm leading-5 text-[#687086]">
                      {product.description || '暂无描述'}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {product.selling_points.slice(0, 4).map((point) => (
                        <span
                          key={point}
                          className="rounded bg-[#eff2ff] px-2 py-0.5 text-xs text-[#5f58ff]"
                        >
                          {point}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
                {!enabledProducts.length && (
                  <EmptyState
                    title="暂无话术来源"
                    description="产品库中启用产品后，这里会展示真实产品卖点并用于生成话术。"
                  />
                )}
              </div>
            </div>
          </div>
        )}

        {activePanel === 'material' && (
          <div className="space-y-5 p-6">
            <section className="rounded-lg border border-[#e2e6ef]">
              <div className="border-b border-[#eef0f4] px-4 py-3 font-medium">
                产品素材
              </div>
              <div className="grid max-h-[380px] gap-3 overflow-auto p-3">
                {products.map((product) => (
                  <div
                    key={productIdentity(product)}
                    className="rounded-lg border border-[#eef0f4] bg-[#fbfcff] p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0 truncate font-medium text-[#34415c]">
                        {product.name}
                      </div>
                      <span
                        className={cn(
                          'shrink-0 rounded px-2 py-0.5 text-xs',
                          product.enabled
                            ? 'bg-[#eaf8f0] text-[#1c8b52]'
                            : 'bg-[#f2f5f8] text-[#7c8496]',
                        )}
                      >
                        {product.enabled ? '启用' : '停用'}
                      </span>
                    </div>
                    <div className="mt-2 text-sm leading-5 text-[#687086]">
                      {product.description || '暂无描述'}
                    </div>
                    <div className="mt-2 grid gap-1 text-xs text-[#7c8496]">
                      <span>分类：{product.category || '暂无'}</span>
                      <span>价格：{product.price || '暂无'}</span>
                      <span>链接：{product.link || '暂无'}</span>
                      <span>适用客户：{compactList(product.audience)}</span>
                    </div>
                  </div>
                ))}
                {!products.length && (
                  <EmptyState
                    title="暂无产品素材"
                    description="AI销售产品库保存真实产品后，素材会同步出现在这里。"
                  />
                )}
              </div>
            </section>

            <section className="rounded-lg border border-[#e2e6ef]">
              <div className="border-b border-[#eef0f4] px-4 py-3 font-medium">
                触达素材
              </div>
              <div className="max-h-[300px] overflow-auto p-3">
                {outreachPlans.map((plan) => (
                  <div
                    key={plan.id || `${plan.name}-${plan.target_id}`}
                    className="mb-3 rounded-lg border border-[#eef0f4] p-3 last:mb-0"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium text-[#34415c]">
                        {plan.name}
                      </div>
                      <span className="rounded bg-[#eff2ff] px-2 py-0.5 text-xs text-[#5f58ff]">
                        {plan.target_type === 'group' ? '群聊' : '私聊'}
                      </span>
                    </div>
                    <div className="mt-2 line-clamp-4 text-sm leading-6 text-[#687086]">
                      {plan.message_template || '暂无触达内容'}
                    </div>
                    <div className="mt-2 text-xs text-[#8b93a5]">
                      下次触达：{formatDate(plan.scheduled_at)}
                    </div>
                  </div>
                ))}
                {!outreachPlans.length && (
                  <EmptyState
                    title="暂无触达素材"
                    description="创建真实触达计划后，这里会展示计划消息和发送目标。"
                  />
                )}
              </div>
            </section>
          </div>
        )}

        {activePanel === 'history' && (
          <div className="space-y-4 p-6">
            <div className="text-sm text-[#7c8496]">客户意图历史</div>
            {intentHistory.map((intent, index) => (
              <div
                key={index}
                className="rounded-lg border border-[#e2e6ef] p-3"
              >
                <div className="font-medium text-[#34415c]">
                  {intentLabel(String(intent.intent || 'general'))}
                </div>
                <div className="mt-1 text-sm leading-6 text-[#687086]">
                  {String(intent.message || '')}
                </div>
                <div className="mt-2 text-xs text-[#8b93a5]">
                  {String(intent.at || '')}
                </div>
              </div>
            ))}
            {!intentHistory.length && (
              <EmptyState
                title="暂无历史记录"
                description="销售插件识别客户意图后，会把真实意图历史记录到这里。"
              />
            )}
          </div>
        )}
      </div>

      <div className="flex w-[76px] shrink-0 flex-col items-center gap-4 border-l border-[#eef0f4] py-4">
        {[
          { panel: 'customer', label: '客户信息', icon: Users },
          { panel: 'talk', label: '话术库', icon: MessageSquare },
          { panel: 'material', label: '素材库', icon: PackagePlus },
          { panel: 'history', label: '历史记录', icon: History },
        ].map((item) => (
          <button
            key={item.panel}
            type="button"
            onClick={() => onPanel(item.panel as RightPanel)}
            className={cn(
              'flex flex-col items-center gap-1 text-sm transition',
              activePanel === item.panel ? 'text-[#5f58ff]' : 'text-[#8d95a6]',
            )}
          >
            <item.icon className="size-6" />
            <span>{item.label}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function CustomersView({
  memories,
  sessions,
  query,
  onQuery,
  onOpenConversation,
}: {
  memories: SalesCustomerMemory[];
  sessions: MonitoringSession[];
  query: string;
  onQuery: (value: string) => void;
  onOpenConversation: (sessionId: string) => void;
}) {
  const sessionMap = useMemo(
    () => new Map(sessions.map((session) => [session.session_id, session])),
    [sessions],
  );
  const filtered = memories.filter((memory) =>
    `${memory.customer_name}${memory.user_id}${memory.summary}${memory.stage}${memory.platform}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  const highIntent = memories.filter(
    (memory) => memory.stage === 'high_intent',
  ).length;
  const handoff = memories.filter(
    (memory) => memory.stage === 'handoff',
  ).length;

  return (
    <div className="grid h-full min-h-0 grid-cols-[280px_minmax(0,1fr)]">
      <aside className="border-r border-[#e2e5ec] bg-white px-5 py-8">
        <h2 className="mb-7 text-xl font-semibold text-[#111827]">客户管理</h2>
        <div className="space-y-2">
          {[
            ['全部客户', memories.length],
            ['高意向客户', highIntent],
            ['已转人工', handoff],
            [
              '考虑中客户',
              memories.filter((memory) => memory.stage === 'consideration')
                .length,
            ],
          ].map(([label, count]) => (
            <div
              key={label}
              className="flex items-center justify-between rounded-lg px-4 py-3 text-[#5d667a]"
            >
              <span>{label}</span>
              <span>{count}</span>
            </div>
          ))}
        </div>
      </aside>
      <main className="min-h-0 overflow-auto bg-white px-7 py-7">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-[#1f2a44]">
            全部客户（{memories.length}）
          </h1>
          <label className="flex h-11 w-[320px] items-center gap-2 rounded-md border border-[#e4e7ef] px-4 text-[#a0a7b7]">
            <Search className="size-5" />
            <input
              value={query}
              onChange={(event) => onQuery(event.target.value)}
              className="w-full bg-transparent outline-none"
              placeholder="搜索客户/摘要/阶段"
            />
          </label>
        </div>

        <section className="mb-6 grid grid-cols-4 gap-4">
          {[
            { label: '客户记忆', value: memories.length, icon: Database },
            { label: '高意向客户', value: highIntent, icon: UserPlus },
            { label: '已转人工', value: handoff, icon: Handshake },
            { label: '真实会话', value: sessions.length, icon: MessageSquare },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-xl border border-[#e0e4ec] p-5"
            >
              <div className="mb-3 flex items-center gap-2 text-[#7c8496]">
                <item.icon className="size-5 text-[#5f58ff]" />
                {item.label}
              </div>
              <div className="text-3xl font-semibold">{item.value}</div>
            </div>
          ))}
        </section>

        <div className="overflow-hidden rounded-lg border border-[#edf0f5]">
          <table className="w-full table-fixed border-collapse text-left">
            <thead>
              <tr className="h-14 bg-[#f8f8fb] text-[#34415c]">
                <th className="w-[220px] px-5 font-semibold">客户</th>
                <th className="px-5 font-semibold">需求摘要</th>
                <th className="w-[180px] px-5 font-semibold">阶段</th>
                <th className="w-[180px] px-5 font-semibold">渠道</th>
                <th className="w-[190px] px-5 font-semibold">最近活跃</th>
                <th className="w-[100px] px-5 font-semibold">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((memory) => {
                const session = sessionMap.get(memory.session_id);
                return (
                  <tr
                    key={memory.session_id}
                    className="h-[76px] border-b border-[#f0f2f6]"
                  >
                    <td className="px-5">
                      <div className="flex items-center gap-3">
                        <Avatar
                          name={
                            memory.customer_name ||
                            memory.user_id ||
                            memory.session_id
                          }
                        />
                        <div className="min-w-0">
                          <div className="truncate font-medium text-[#34415c]">
                            {memory.customer_name ||
                              memory.user_id ||
                              memory.session_id}
                          </div>
                          <div className="truncate text-xs text-[#8b93a5]">
                            {memory.session_id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="truncate px-5 text-[#687086]">
                      {memory.summary || '暂无摘要'}
                    </td>
                    <td className="px-5">
                      <span className="rounded-full bg-[#f2f1ff] px-3 py-1 text-[#5f58ff]">
                        {stageLabel(memory.stage)}
                      </span>
                    </td>
                    <td className="px-5 text-[#687086]">
                      {platformLabel(session?.platform || memory.platform)}
                    </td>
                    <td className="px-5 text-[#687086]">
                      {formatDate(memory.last_seen_at)}
                    </td>
                    <td className="px-5">
                      <button
                        type="button"
                        onClick={() => onOpenConversation(memory.session_id)}
                        className="flex size-8 items-center justify-center rounded-md border border-[#e4e7ef] text-[#697287]"
                      >
                        <Eye className="size-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!filtered.length && (
            <EmptyState
              title="暂无真实客户"
              description="客户记忆由销售插件根据真实消息沉淀；当前没有符合条件的记录。"
            />
          )}
        </div>
      </main>
    </div>
  );
}

function WorkbenchView({
  overview,
  products,
  handoffs,
  outreachPlans,
  sessions,
  loading,
  onRefresh,
  onRunOutreach,
}: {
  overview: SalesOverview | null;
  products: SalesProduct[];
  handoffs: SalesHandoff[];
  outreachPlans: SalesOutreachPlan[];
  sessions: MonitoringSession[];
  loading: boolean;
  onRefresh: () => void;
  onRunOutreach: () => void;
}) {
  const metrics = [
    {
      label: '产品库',
      value: overview?.products_count ?? products.length,
      icon: Database,
      desc: '来自 AI 销售产品数据库',
    },
    {
      label: '待人工接入',
      value: overview?.open_handoffs_count ?? handoffs.length,
      icon: Handshake,
      desc: '真实转人工队列',
    },
    {
      label: '触达计划',
      value: overview?.outreach_plans_count ?? outreachPlans.length,
      icon: CalendarClock,
      desc: '定时产品触达任务',
    },
    {
      label: '监控会话',
      value: sessions.length,
      icon: MessageSquare,
      desc: '机器人真实会话记录',
    },
  ];

  return (
    <main className="min-h-0 overflow-auto bg-[#edf2f8] px-7 py-7">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[#111827]">工作台</h1>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 rounded-lg border border-[#d8deea] bg-white px-4 py-2 text-[#34415c]"
          >
            {loading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            刷新真实数据
          </button>
          <button
            type="button"
            onClick={() => {
              window.location.href = '/home/sales';
            }}
            className="inline-flex items-center gap-2 rounded-lg bg-[#5f58ff] px-4 py-2 text-white"
          >
            <PackagePlus className="size-4" />
            管理产品库
          </button>
        </div>
      </div>
      <section className="grid w-[1180px] grid-cols-4 gap-5">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded-2xl border border-[#d8deea] bg-white p-6 shadow-sm"
          >
            <metric.icon className="mb-6 size-9 text-[#5f58ff]" />
            <div className="text-3xl font-semibold text-[#111827]">
              {metric.value}
            </div>
            <div className="mt-2 text-lg font-semibold text-[#111827]">
              {metric.label}
            </div>
            <div className="mt-2 text-sm leading-6 text-[#8b94a7]">
              {metric.desc}
            </div>
          </div>
        ))}
      </section>

      <section className="mt-6 grid w-[1180px] grid-cols-2 gap-5">
        <div className="rounded-2xl border border-[#d8deea] bg-white p-6">
          <div className="mb-4 flex items-center gap-2 text-xl font-semibold">
            <Handshake className="size-6 text-[#5f58ff]" />
            待接入客户
          </div>
          <div className="max-h-80 divide-y divide-[#edf0f5] overflow-auto">
            {handoffs.map((handoff) => (
              <div key={handoff.id} className="py-3">
                <div className="font-medium text-[#34415c]">
                  {handoff.user_id || handoff.session_id}
                </div>
                <div className="mt-1 line-clamp-2 text-sm text-[#687086]">
                  {handoff.last_message || handoff.reason}
                </div>
              </div>
            ))}
            {!handoffs.length && (
              <div className="py-10 text-center text-sm text-[#8b93a5]">
                当前没有待人工接入
              </div>
            )}
          </div>
        </div>
        <div className="rounded-2xl border border-[#d8deea] bg-white p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xl font-semibold">
              <CalendarClock className="size-6 text-[#5f58ff]" />
              定时触达
            </div>
            <button
              type="button"
              onClick={onRunOutreach}
              className="rounded-lg border border-[#5f58ff] px-3 py-1.5 text-[#5f58ff]"
            >
              执行到期任务
            </button>
          </div>
          <div className="max-h-80 divide-y divide-[#edf0f5] overflow-auto">
            {outreachPlans.map((plan) => (
              <div key={plan.id} className="py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-[#34415c]">{plan.name}</div>
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-xs',
                      plan.enabled
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-slate-100 text-slate-500',
                    )}
                  >
                    {plan.enabled ? '启用' : '停用'}
                  </span>
                </div>
                <div className="mt-1 text-sm text-[#687086]">
                  下次推送：{formatDate(plan.scheduled_at)}
                </div>
              </div>
            ))}
            {!outreachPlans.length && (
              <div className="py-10 text-center text-sm text-[#8b93a5]">
                暂无触达计划
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

export default function SalesChatPage() {
  const [mainView, setMainView] = useState<MainView>('conversation');
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [activePanel, setActivePanel] = useState<RightPanel>('customer');
  const [overview, setOverview] = useState<SalesOverview | null>(null);
  const [products, setProducts] = useState<SalesProduct[]>([]);
  const [memories, setMemories] = useState<SalesCustomerMemory[]>([]);
  const [handoffs, setHandoffs] = useState<SalesHandoff[]>([]);
  const [outreachPlans, setOutreachPlans] = useState<SalesOutreachPlan[]>([]);
  const [sessions, setSessions] = useState<MonitoringSession[]>([]);
  const [messages, setMessages] = useState<MonitoringMessage[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [conversationQuery, setConversationQuery] = useState('');
  const [customerQuery, setCustomerQuery] = useState('');
  const [accountFilter, setAccountFilter] = useState('all');
  const [messageTypeFilter, setMessageTypeFilter] = useState('all');
  const [replyModeFilter, setReplyModeFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [messageLoading, setMessageLoading] = useState(false);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [memoryDraft, setMemoryDraft] = useState<CustomerProfileDraft>(
    makeProfileDraft(undefined),
  );
  const [savingMemory, setSavingMemory] = useState(false);

  const conversations = useMemo(
    () => buildConversations(sessions, memories, handoffs),
    [handoffs, memories, sessions],
  );

  const accountOptions = useMemo(
    () => uniqueLabels(conversations.map(conversationAccountLabel)),
    [conversations],
  );

  const messageTypeOptions = useMemo(
    () => uniqueLabels(conversations.map(conversationMessageTypeLabel)),
    [conversations],
  );

  const replyModeOptions = useMemo(
    () => uniqueLabels(conversations.map(conversationReplyModeLabel)),
    [conversations],
  );

  const selectedConversation = useMemo(
    () =>
      conversations.find(
        (conversation) => conversation.sessionId === selectedSessionId,
      ),
    [conversations, selectedSessionId],
  );

  const currentUser =
    userInfo?.user ||
    (typeof window !== 'undefined' ? localStorage.getItem('userEmail') : '') ||
    'sales-admin';

  const loadDashboard = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      await initializeUserInfo();
      const monitoringRangeStart = new Date(
        Date.now() - 30 * 24 * 60 * 60 * 1000,
      ).toISOString();
      const [
        overviewData,
        productResp,
        memoryResp,
        handoffResp,
        outreachResp,
        monitoringResp,
      ] = await Promise.all([
        httpClient.getSalesOverview(),
        httpClient.getSalesProducts(),
        httpClient.getSalesMemories(),
        httpClient.getSalesHandoffs('open'),
        httpClient.getSalesOutreachPlans(),
        httpClient.getMonitoringData({
          startTime: monitoringRangeStart,
          endTime: new Date().toISOString(),
          limit: 100,
        }),
      ]);
      setOverview(overviewData);
      setProducts(productResp.products || []);
      setMemories(memoryResp.memories || []);
      setHandoffs(handoffResp.handoffs || []);
      setOutreachPlans(outreachResp.plans || []);
      setSessions((monitoringResp.sessions || []) as MonitoringSession[]);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  const loadMessages = useCallback(async (sessionId: string) => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    setMessageLoading(true);
    try {
      const resp = await httpClient.getSessionMessages(sessionId, 200, 0);
      const sorted = [...(resp.messages || [])].sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      );
      setMessages(sorted as MonitoringMessage[]);
    } catch (error) {
      setMessages([]);
      toast.error(errorMessage(error));
    } finally {
      setMessageLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
    const timer = window.setInterval(() => {
      void loadDashboard(false);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [loadDashboard]);

  useEffect(() => {
    if (!selectedSessionId && conversations[0]?.sessionId) {
      setSelectedSessionId(conversations[0].sessionId);
    }
  }, [conversations, selectedSessionId]);

  useEffect(() => {
    void loadMessages(selectedSessionId);
  }, [loadMessages, selectedSessionId]);

  useEffect(() => {
    setMemoryDraft(makeProfileDraft(selectedConversation?.memory));
  }, [selectedConversation?.memory]);

  const openHandoff = async () => {
    if (!selectedConversation) return;
    try {
      await httpClient.openSalesHandoffFromSession({
        session_id: selectedConversation.sessionId,
        reason: '人工主动介入',
        assigned_to: currentUser,
      });
      await loadDashboard(false);
      toast.success('已加入人工接入队列');
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const sendReply = async () => {
    if (!selectedConversation || !draft.trim()) return;
    setSending(true);
    try {
      const reply = draft.trim();
      await httpClient.replySalesHandoffFromSession({
        session_id: selectedConversation.sessionId,
        reply,
        assigned_to: currentUser,
      });
      setDraft('');
      await Promise.all([
        loadDashboard(false),
        loadMessages(selectedConversation.sessionId),
      ]);
      toast.success('人工回复已通过机器人发送');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSending(false);
    }
  };

  const saveMemory = async () => {
    if (!selectedConversation) return;
    setSavingMemory(true);
    try {
      const { customer_name, stage, summary, ...profile } = memoryDraft;
      await httpClient.updateSalesMemory(selectedConversation.sessionId, {
        customer_name,
        stage,
        summary,
        profile,
      });
      await loadDashboard(false);
      toast.success('客户信息已保存');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSavingMemory(false);
    }
  };

  const openConversationFromCustomer = (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setMainView('conversation');
  };

  const runOutreach = async () => {
    try {
      const result = await httpClient.runDueSalesOutreach();
      await loadDashboard(false);
      toast.success(`已执行 ${result.sent} 条到期触达`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  if (mainView === 'customers') {
    return (
      <Shell activeView={mainView} onViewChange={setMainView}>
        <CustomersView
          memories={memories}
          sessions={sessions}
          query={customerQuery}
          onQuery={setCustomerQuery}
          onOpenConversation={openConversationFromCustomer}
        />
      </Shell>
    );
  }

  if (mainView === 'workbench') {
    return (
      <Shell activeView={mainView} onViewChange={setMainView}>
        <WorkbenchView
          overview={overview}
          products={products}
          handoffs={handoffs}
          outreachPlans={outreachPlans}
          sessions={sessions}
          loading={loading}
          onRefresh={() => void loadDashboard()}
          onRunOutreach={() => void runOutreach()}
        />
      </Shell>
    );
  }

  return (
    <Shell activeView={mainView} onViewChange={setMainView}>
      <div
        className={cn(
          'grid h-full min-h-0',
          rightPanelOpen
            ? 'grid-cols-[388px_minmax(520px,1fr)_430px]'
            : 'grid-cols-[388px_minmax(520px,1fr)]',
        )}
      >
        <ConversationList
          conversations={conversations}
          selectedSessionId={selectedSessionId}
          query={conversationQuery}
          accountFilter={accountFilter}
          messageTypeFilter={messageTypeFilter}
          replyModeFilter={replyModeFilter}
          accountOptions={accountOptions}
          messageTypeOptions={messageTypeOptions}
          replyModeOptions={replyModeOptions}
          loading={loading}
          onQuery={setConversationQuery}
          onAccountFilter={setAccountFilter}
          onMessageTypeFilter={setMessageTypeFilter}
          onReplyModeFilter={setReplyModeFilter}
          onSelect={setSelectedSessionId}
        />
        <ChatCenter
          conversation={selectedConversation}
          messages={messages}
          loading={messageLoading}
          draft={draft}
          sending={sending}
          onDraft={setDraft}
          onSend={() => void sendReply()}
          onRefresh={() => {
            void loadDashboard(false);
            void loadMessages(selectedSessionId);
          }}
          onOpenHandoff={() => void openHandoff()}
        />
        {rightPanelOpen ? (
          <RightPanelContent
            activePanel={activePanel}
            conversation={selectedConversation}
            products={products}
            outreachPlans={outreachPlans}
            memoryDraft={memoryDraft}
            savingMemory={savingMemory}
            onPanel={setActivePanel}
            onDraft={setMemoryDraft}
            onSaveMemory={() => void saveMemory()}
            onClose={() => setRightPanelOpen(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setRightPanelOpen(true)}
            className="absolute right-4 top-24 rounded-lg border border-[#dde2ec] bg-white px-3 py-2 text-sm text-[#5f58ff] shadow-sm"
          >
            打开客户信息
          </button>
        )}
      </div>
    </Shell>
  );
}
