import { useMemo, useState } from 'react';
import {
  Archive,
  AtSign,
  BriefcaseBusiness,
  ChevronDown,
  CircleCheck,
  Clock,
  FileText,
  History,
  ImageIcon,
  MessageSquare,
  PenLine,
  RotateCcw,
  Search,
  Send,
  Settings,
  SlidersHorizontal,
  Smile,
  Sparkles,
  SquarePen,
  UserPlus,
  Users,
  Video,
  X,
} from 'lucide-react';

import { cn } from '@/lib/utils';

type Conversation = {
  id: string;
  name: string;
  preview: string;
  time: string;
  unread: number;
  replyMode: 'AI回复' | '人工回复';
  owner: string;
  avatarTone: string;
  active?: boolean;
};

type ChatMessage = {
  id: string;
  author: string;
  time: string;
  role: 'customer' | 'agent';
  body: string;
};

type CustomerField = {
  label: string;
  value: string;
};

type RightPanel = 'customer' | 'talk' | 'material' | 'assistant' | 'history';
type FilterKey = 'account' | 'type' | 'reply' | null;

const conversations: Conversation[] = [
  {
    id: 'gd',
    name: 'gd@微信',
    preview: '邀请你 加入会话',
    time: '9:53',
    unread: 8,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-slate-900 to-emerald-700',
  },
  {
    id: 'ning',
    name: 'Ning@微信',
    preview: '邀请你 加入会话',
    time: '9:53',
    unread: 6,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-amber-400 to-orange-500',
  },
  {
    id: 'sales-a',
    name: '独到-小蔡@独到...',
    preview: '哦哦 明白 ~ 现在是...',
    time: '星期五 15:35',
    unread: 8,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-indigo-400 to-sky-300',
  },
  {
    id: 'jiushi',
    name: '旧石@微信',
    preview: '好的 褚总 ~ 收到...',
    time: '星期四 17:47',
    unread: 15,
    replyMode: '人工回复',
    owner: '',
    avatarTone: 'from-slate-700 to-slate-400',
    active: true,
  },
  {
    id: 'liuhong',
    name: '刘婷@微信',
    preview: '明日的 ~ 那其实正...',
    time: '星期四 14:45',
    unread: 10,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-cyan-300 to-blue-500',
  },
  {
    id: 'zhaolong',
    name: '赵龙@微信',
    preview: '您好您好 ~ 您...',
    time: '星期四 14:38',
    unread: 8,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-blue-600 to-indigo-500',
  },
  {
    id: 'yazhen',
    name: '雅云@微信',
    preview: '可以的-您这个私...',
    time: '星期二 14:39',
    unread: 8,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-yellow-100 to-amber-500',
  },
  {
    id: 'wang',
    name: '王富贵儿@微信',
    preview: '好嘞 了解 ~ 我还是...',
    time: '星期三 13:51',
    unread: 13,
    replyMode: '人工回复',
    owner: '',
    avatarTone: 'from-stone-300 to-stone-700',
  },
  {
    id: 'chun',
    name: '纯粮战士@微信',
    preview: '邀请你 加入会话',
    time: '星期三 11:20',
    unread: 6,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-neutral-500 to-zinc-900',
  },
  {
    id: 'xie',
    name: '蟹蟹没有钳@...',
    preview: '邀请你 加入会话',
    time: '星期二 16:15',
    unread: 6,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-green-700 to-slate-900',
  },
  {
    id: 'f',
    name: 'F. @微信',
    preview: '邀请你 加入会话',
    time: '星期二 16:15',
    unread: 6,
    replyMode: 'AI回复',
    owner: 'SDR',
    avatarTone: 'from-rose-200 to-orange-500',
  },
];

const seedMessages: Record<string, ChatMessage[]> = {
  jiushi: [
    {
      id: 'm1',
      author: '旧石@微信',
      time: '2026-06-04 17:47:15',
      role: 'customer',
      body: '15805145079',
    },
    {
      id: 'm2',
      author: '张小琪@独到科技【AI】',
      time: '2026-06-04 17:47:44',
      role: 'agent',
      body: '好的褚总~收到\n\n我这边拉个群 让我们负责业务的客户经理接着跟您聊~',
    },
  ],
};

const baseFields: CustomerField[] = [
  { label: '姓名', value: '褚' },
  { label: '职位', value: '暂无' },
  { label: '电话/手机号', value: '15805145079' },
  { label: '微信号', value: '暂无' },
  { label: '邮箱', value: '暂无' },
  { label: '所在地', value: '暂无' },
  { label: '公司名称', value: '湖州云梯科技' },
  { label: '行业类别', value: '图书出版行业，...' },
  { label: '组织规模', value: '暂无' },
  { label: '融资阶段', value: '暂无' },
  { label: '公司技术栈', value: '暂无' },
  { label: '申请专业', value: '暂无' },
  { label: '客单价', value: '暂无' },
];

const aiTags = [
  '湖州云梯科技',
  '褚总',
  '15805145079',
  '信息完整度：是',
  '紧急度：中',
];
const manualTags = [
  '未购买套餐',
  '中性用户',
  'AI打标签测试-低意向',
  'DearLink Plus',
  '销售自动化',
  '线索筛选',
  '客户意图识别',
];

const materialItems = [
  {
    title: '文本_22',
    author: '化俊杰',
    time: '2026-03-09 15:53',
    text: '正在为某客户策划激活方案，通过DearLink，完成34%的激活率，看起来非常可行，看看这个对你的业务有帮助吗？',
  },
  {
    title: '文本_21',
    author: '化俊杰',
    time: '2026-01-28 10:20',
    text: '您好呀 ~ 我是小玥，主要负责产品方面咨询，您想咨询哪方面的问题呀',
  },
  {
    title: '激活第四次_0127',
    author: '化俊杰',
    time: '2026-01-26 15:33',
    text: '刚才刷朋友圈看到老客户发的上图，属实被这个钩子给吓了一跳。之前虽然跟您提过AI能提效...',
  },
  {
    title: '张小琪-激活第一条',
    author: '小琪',
    time: '2026-01-23 15:24',
    text: '今早看了个银行案例受到了启发：只用3条短消息+1个提问，转化率反而涨了37%。',
  },
  {
    title: '第三次激活',
    author: '化俊杰',
    time: '2026-01-22 09:57',
    text: '昨晚把 导流→接待→转化 彻底跑通，全程没掉链子，业绩直接翻3倍。',
  },
  {
    title: '第二次激活内容',
    author: '化俊杰',
    time: '2026-01-15 15:15',
    text: '天呐！你敢信“AI话术库”比培训10个销售更狠！凌晨抓取217条真实咨询数据...',
  },
];

function Avatar({
  name,
  tone,
  size = 'md',
}: {
  name: string;
  tone: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
}) {
  const initial = name.slice(0, 1);
  return (
    <div
      className={cn(
        'relative shrink-0 rounded-xl bg-gradient-to-br text-white shadow-sm',
        tone,
        size === 'xs' && 'size-7 text-xs',
        size === 'sm' && 'size-9 text-sm',
        size === 'md' && 'size-12 text-base',
        size === 'lg' && 'size-14 text-lg',
      )}
    >
      <div className="flex h-full w-full items-center justify-center font-semibold">
        {initial}
      </div>
      {size !== 'xs' && (
        <span className="absolute -bottom-0.5 -right-0.5 size-3 rounded-[3px] border-2 border-white bg-[#45cf72]" />
      )}
    </div>
  );
}

function AppTopBar() {
  return (
    <header className="grid grid-cols-[456px_1fr_508px] items-center border-b border-[#dde0e6] bg-[#eef0f3] px-5">
      <div className="text-2xl font-bold tracking-tight text-[#2b303b]">
        DearLink.
        <span className="font-semibold text-[#5a55ff]"> Plus</span>
      </div>
      <div />
      <div className="flex items-center justify-end gap-5">
        <button
          type="button"
          className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-base text-[#111827] shadow-sm"
        >
          <span className="flex h-5 w-9 items-center rounded-full bg-[#5f62ff] p-0.5">
            <span className="size-4 translate-x-4 rounded-full bg-white shadow" />
          </span>
          接待客户
        </button>
        <div className="size-11 rounded-full bg-[#e2e9f1] p-1">
          <div className="h-full w-full rounded-full bg-gradient-to-br from-[#dfe8ef] to-[#f6fbff]" />
        </div>
        <button
          type="button"
          className="flex items-center gap-2 text-lg text-[#202a3c]"
        >
          珊珊
          <ChevronDown className="size-5 text-[#8c93a3]" />
        </button>
      </div>
    </header>
  );
}

function AppRail() {
  const items = [
    { label: '对话', icon: MessageSquare, active: true },
    { label: '客户', icon: Users },
    { label: '工作台', icon: BriefcaseBusiness },
    { label: '设置', icon: Settings },
  ];

  return (
    <nav className="border-r border-[#dde0e6] bg-[#eef0f3] py-2">
      <div className="flex flex-col items-center gap-2">
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            className={cn(
              'flex w-12 flex-col items-center gap-1 rounded-xl py-2 text-xs transition',
              item.active ? 'bg-[#e3e4ff] text-[#5a55ff]' : 'text-[#8e96a6]',
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

function FilterButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-base text-[#283248] transition',
        active && 'bg-[#f0f1f5]',
      )}
    >
      {label}
      <ChevronDown className="size-4" />
    </button>
  );
}

function FilterPopover({
  openFilter,
}: {
  openFilter: Exclude<FilterKey, null>;
}) {
  if (openFilter === 'account') {
    return (
      <div className="absolute left-4 top-[116px] z-20 w-[286px] rounded-lg bg-white p-3 shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
        <div className="flex items-center gap-3 rounded-md bg-[#f7f8fb] px-3 py-3 text-sm text-[#374151]">
          <Avatar name="张小琪" tone="from-slate-600 to-slate-800" size="xs" />
          <span>张小琪 @独到科技</span>
        </div>
      </div>
    );
  }

  if (openFilter === 'type') {
    return (
      <div className="absolute left-[148px] top-[116px] z-20 w-28 rounded-lg bg-white py-2 text-base text-[#202a3c] shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
        <button
          type="button"
          className="block w-full px-4 py-2 text-left hover:bg-[#f6f7fb]"
        >
          私聊
        </button>
        <button
          type="button"
          className="block w-full px-4 py-2 text-left hover:bg-[#f6f7fb]"
        >
          群聊
        </button>
      </div>
    );
  }

  return (
    <div className="absolute left-[250px] top-[116px] z-20 w-36 rounded-lg bg-white p-3 text-base text-[#202a3c] shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
      {['AI回复', '人工回复', 'SDR进程中'].map((item) => (
        <label key={item} className="flex items-center gap-2 py-1.5">
          <span className="size-4 rounded border border-[#d7dbe4]" />
          {item}
        </label>
      ))}
    </div>
  );
}

function ConversationRow({
  item,
  selected,
  onClick,
}: {
  item: Conversation;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'grid w-full grid-cols-[54px_1fr] gap-3 rounded-xl px-3 py-2.5 text-left transition',
        selected ? 'bg-[#eceef3]' : 'hover:bg-[#f6f7fb]',
      )}
    >
      <div className="relative">
        <Avatar name={item.name} tone={item.avatarTone} size="md" />
        <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[#ef5148] px-1 text-xs font-semibold leading-none text-white">
          {item.unread}
        </span>
      </div>
      <div className="min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-base font-medium text-[#566070]">
            {item.name}
          </p>
          <span className="shrink-0 text-sm text-[#7b84a0]">{item.time}</span>
        </div>
        <p className="mt-1 truncate text-base text-[#596272]">{item.preview}</p>
        <div className="mt-2 flex items-center justify-end gap-2">
          <span className="rounded-md bg-[#ecebff] px-1.5 py-0.5 text-xs text-[#625cff]">
            {item.replyMode}
          </span>
          {item.owner && (
            <span className="rounded-md bg-[#fff0d8] px-1.5 py-0.5 text-xs text-[#e18a30]">
              {item.owner}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

function ConversationList({
  selectedConversation,
  openFilter,
  onFilter,
  onSelect,
}: {
  selectedConversation: Conversation;
  openFilter: FilterKey;
  onFilter: (filter: FilterKey) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="relative min-h-0 border-r border-[#dde0e6] bg-white">
      <div className="flex h-16 items-center justify-between border-b border-[#eef0f3] px-5">
        <h1 className="text-xl font-semibold text-[#1f2a44]">对话</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="rounded-xl border border-[#dbe0ea] p-2 text-[#8c93a3]"
          >
            <UserPlus className="size-5" />
          </button>
          <button
            type="button"
            className="rounded-xl border border-[#dbe0ea] p-2 text-[#8c93a3]"
          >
            <FileText className="size-5" />
          </button>
        </div>
      </div>

      <div className="space-y-5 px-5 py-5">
        <label className="relative block">
          <Search className="absolute right-3 top-1/2 size-5 -translate-y-1/2 text-[#9aa3b5]" />
          <input
            className="h-10 w-full rounded-lg border border-[#dce1ea] bg-white px-4 pr-10 text-base outline-none placeholder:text-[#9aa3b5]"
            placeholder="搜索备注/昵称/群名"
          />
        </label>
        <div className="flex items-center justify-between">
          <FilterButton
            label="所属账号"
            active={openFilter === 'account'}
            onClick={() =>
              onFilter(openFilter === 'account' ? null : 'account')
            }
          />
          <FilterButton
            label="消息类型"
            active={openFilter === 'type'}
            onClick={() => onFilter(openFilter === 'type' ? null : 'type')}
          />
          <FilterButton
            label="回复方式"
            active={openFilter === 'reply'}
            onClick={() => onFilter(openFilter === 'reply' ? null : 'reply')}
          />
        </div>
      </div>

      {openFilter && <FilterPopover openFilter={openFilter} />}

      <div className="h-[calc(100%-10.5rem)] overflow-y-auto px-3 pb-4">
        <div className="space-y-1">
          {conversations.map((conversation) => (
            <ConversationRow
              key={conversation.id}
              item={conversation}
              selected={conversation.id === selectedConversation.id}
              onClick={() => onSelect(conversation.id)}
            />
          ))}
        </div>
      </div>
    </aside>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isAgent = message.role === 'agent';
  return (
    <div className="flex gap-3 px-9">
      <Avatar
        name={message.author}
        tone={
          isAgent
            ? 'from-slate-600 to-slate-800'
            : 'from-slate-700 to-slate-400'
        }
        size="sm"
      />
      <div className="max-w-[560px]">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-sm text-[#626b7c]">
          <span>{message.author}</span>
          <span>{message.time}</span>
        </div>
        <div className="whitespace-pre-wrap rounded-xl bg-white px-5 py-4 text-base leading-7 text-[#293241] shadow-sm">
          {message.body}
        </div>
      </div>
    </div>
  );
}

function InsightCard() {
  const rows = [
    ['湖州云梯科技', '褚总', '15805145079'],
    ['信息完整度：是', '紧急度：中'],
    ['亲爱的链接加', '销售自动化', '线索筛选'],
    ['客户意图识别'],
  ];

  return (
    <div className="mx-auto w-[430px] rounded-xl bg-white/70 px-8 py-5 shadow-sm">
      <div className="mb-4 rounded-full border border-[#e1e4ed] bg-white/70 px-5 py-3 text-center text-base font-semibold text-[#2f3442]">
        <Sparkles className="mr-2 inline size-4 text-[#5d57ff]" />
        K12教辅企业咨询AI销售智能体
      </div>
      <div className="space-y-2">
        {rows.map((group) => (
          <div key={group.join('-')} className="flex flex-wrap gap-2">
            {group.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-[#ececff] px-3 py-1 text-base text-[#5e58ff]"
              >
                {tag}
              </span>
            ))}
          </div>
        ))}
      </div>
      <p className="mt-4 text-base leading-7 text-[#4d5668]">
        客户来自湖州云梯科技，从事K12教辅图书及课程销售，与学而思、新东方合作，咨询DearLink
        Plus销售智能体，用于提升线索筛选和转化效率。已提供姓名（褚总）和电话。
      </p>
      <p className="mt-2 text-base leading-7 text-[#4d5668]">
        策略推荐：高意向客户，建议尽快电话或微信联系，结合教育行业案例进行演示，突出线索筛选和转化提升效果。
      </p>
    </div>
  );
}

function ChatCenter({
  selectedConversation,
  messages,
  draft,
  aiReply,
  onDraft,
  onSend,
  onToggleAI,
}: {
  selectedConversation: Conversation;
  messages: ChatMessage[];
  draft: string;
  aiReply: boolean;
  onDraft: (value: string) => void;
  onSend: () => void;
  onToggleAI: () => void;
}) {
  return (
    <main className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)_216px] bg-[#dedee6]">
      <header className="flex items-center justify-between border-b border-[#dde0e6] bg-white px-6">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate text-xl font-semibold text-[#1f2a44]">
            {selectedConversation.name}
          </h2>
          <SquarePen className="size-5 shrink-0 text-[#778198]" />
          <span className="shrink-0 text-base text-[#4b5568]">来源-微信</span>
        </div>
        <div className="flex items-center gap-5">
          <CircleCheck className="size-5 text-[#8a93a6]" />
          <RotateCcw className="size-5 text-[#8a93a6]" />
          <button
            type="button"
            className="rounded-md border border-[#625cff] px-4 py-2 text-base font-medium text-[#5a55ff]"
          >
            结束对话
          </button>
        </div>
      </header>

      <div className="min-h-0 overflow-y-auto py-8">
        <div className="space-y-8">
          {messages.slice(0, 1).map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <InsightCard />
          {messages.slice(1).map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>
      </div>

      <footer className="border-t border-[#dde0e6] bg-white px-6 py-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-5 text-[#98a1b4]">
            <Smile className="size-5" />
            <AtSign className="size-5" />
            <ImageIcon className="size-5" />
            <Video className="size-5" />
          </div>
          <label className="flex items-center gap-3 text-base font-medium text-[#0f172a]">
            <button
              type="button"
              role="switch"
              aria-checked={aiReply}
              onClick={onToggleAI}
              className={cn(
                'flex h-5 w-10 items-center rounded-full p-0.5 transition',
                aiReply ? 'bg-[#8f96ad]' : 'bg-[#c9cfda]',
              )}
            >
              <span
                className={cn(
                  'size-4 rounded-full bg-white shadow transition',
                  aiReply && 'translate-x-5',
                )}
              />
            </button>
            AI回复
          </label>
        </div>
        <div className="relative">
          <textarea
            value={draft}
            onChange={(event) => onDraft(event.target.value)}
            className="h-34 w-full resize-none rounded-xl bg-[#f4f6fa] px-4 py-3 pr-24 text-base leading-6 text-[#334155] outline-none placeholder:text-[#8f98aa]"
            placeholder="使用 Enter 发送消息，使用 Shift + Enter 换行"
          />
          <div className="absolute bottom-3 right-3 flex items-center gap-3">
            <span className="text-base text-[#7d8699]">{draft.length}/600</span>
            <button
              type="button"
              onClick={onSend}
              className="rounded-md bg-[#5f5cf6] px-4 py-2 text-base font-medium text-white"
            >
              发送
            </button>
          </div>
        </div>
      </footer>
    </main>
  );
}

function PanelHeader({ title }: { title: string }) {
  return (
    <div className="flex h-16 items-center justify-between border-b border-[#eef0f3] px-6">
      <h2 className="text-xl font-medium text-[#1f2a44]">{title}</h2>
      <button type="button" className="rounded-md p-1 text-[#8a8f9c]">
        <X className="size-5" />
      </button>
    </div>
  );
}

function Tag({ children }: { children: string }) {
  return (
    <span className="rounded-full bg-[#f1f0ff] px-3 py-1 text-base text-[#5f58ff]">
      {children}
    </span>
  );
}

function CustomerInfoPanel({ conversation }: { conversation: Conversation }) {
  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="客户信息" />
      <div className="min-h-0 overflow-y-auto px-6 py-5">
        <div className="flex items-center gap-3">
          <Avatar
            name={conversation.name}
            tone={conversation.avatarTone}
            size="md"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <p className="truncate text-xl font-semibold text-[#273247]">
                {conversation.name}
              </p>
              <button
                type="button"
                className="flex items-center gap-1 rounded-md bg-[#f0efff] px-3 py-1.5 text-base text-[#5f58ff]"
              >
                意向客户
                <ChevronDown className="size-4" />
              </button>
            </div>
            <p className="mt-3 flex items-center gap-2 text-base text-[#7b8495]">
              所属账号
              <span className="size-2 rounded-full bg-[#34bf64]" />
              <span className="text-[#475467]">张小琪 独到科技</span>
            </p>
          </div>
        </div>

        <section className="mt-7">
          <div className="mb-5 flex items-center gap-2 text-xl font-medium text-[#1f2937]">
            <ChevronDown className="size-5 fill-[#111827] text-[#111827]" />
            基础信息
          </div>
          <div className="space-y-5">
            {baseFields.map((field) => (
              <div
                key={field.label}
                className="grid grid-cols-[116px_1fr] items-center gap-4 text-base"
              >
                <span className="text-[#7b8495]">{field.label}</span>
                <span className="flex min-w-0 items-center gap-2 text-[#4a5568]">
                  <span className="truncate">{field.value}</span>
                  <PenLine className="size-4 shrink-0 text-[#9ba3b2]" />
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-8 border-t border-[#eef0f3] pt-5">
          <div className="mb-5 flex items-center gap-2 text-xl font-medium text-[#1f2937]">
            <ChevronDown className="size-5 fill-[#111827] text-[#111827]" />
            标签信息
          </div>
          <div className="mb-3 flex items-center justify-between text-base">
            <span className="text-[#7b8495]">AI标签</span>
            <button type="button" className="text-[#5f58ff]">
              标签操作
            </button>
          </div>
          <div className="mb-5 flex flex-wrap gap-2">
            {aiTags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
          <div className="mb-3 flex items-center justify-between text-base">
            <span className="text-[#7b8495]">标签</span>
            <button type="button" className="text-[#5f58ff]">
              标签操作
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {manualTags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
          <div className="mt-7 text-base text-[#7b8495]">备注信息</div>
          <PenLine className="mt-2 size-5 text-[#6d7894]" />
        </section>

        <section className="mt-8 border-t border-[#eef0f3] pt-5">
          <div className="mb-8 flex items-center gap-2 text-xl font-medium text-[#1f2937]">
            <ChevronDown className="size-5 fill-[#111827] text-[#111827]" />
            用户动态
          </div>
          <div className="text-base text-[#7b8495]">访问精灵次数</div>
          <div className="mt-3 text-xl font-semibold text-[#0f172a]">0</div>
          <div className="mt-40 text-center text-lg text-[#a0a7b5]">
            暂无访问记录
          </div>
        </section>
      </div>
    </div>
  );
}

function TalkPanel() {
  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="话术库" />
      <div className="min-h-0 overflow-y-auto px-4 py-4">
        <div className="mb-4 flex items-center border-b border-[#e4e8f0] text-lg">
          <button
            type="button"
            className="border-b-2 border-[#5f58ff] px-2 py-3 text-[#5f58ff]"
          >
            团队话术库
          </button>
          <button type="button" className="px-8 py-3 text-[#0f172a]">
            个人话术库
          </button>
          <SlidersHorizontal className="ml-auto size-5 text-[#8d95a6]" />
        </div>
        <label className="relative mb-4 block">
          <Search className="absolute right-3 top-1/2 size-5 -translate-y-1/2 text-[#99a2b3]" />
          <input
            className="h-11 w-full rounded-lg border border-[#dce1ea] px-4 text-base outline-none"
            placeholder="搜索标题/内容"
          />
        </label>
        {[
          ['全部话术', '2'],
          ['新客引导话术', '1'],
          ['老客复购营销话术', '1'],
          ['活动话术', '0'],
          ['情绪安抚话术', '0'],
        ].map(([title, count]) => (
          <div
            key={title}
            className="border-b border-[#eef0f3] py-4 text-xl text-[#1f2a44]"
          >
            <span className="mr-3 text-sm">▶</span>
            {title}（{count}）
          </div>
        ))}
      </div>
    </div>
  );
}

function MaterialPanel() {
  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="素材库" />
      <div className="min-h-0 overflow-y-auto px-3 py-4">
        <div className="mb-3 flex items-center gap-6 border-b border-[#e4e8f0] text-base text-[#1f2a44]">
          {[
            '文本',
            '图片',
            '小程序',
            '链接',
            '视频',
            '视频号',
            '语音',
            '文件',
          ].map((tab, index) => (
            <button
              key={tab}
              type="button"
              className={cn(
                'pb-3',
                index === 0 && 'border-b-2 border-[#111827]',
              )}
            >
              {tab}
            </button>
          ))}
        </div>
        <label className="relative mb-3 block">
          <Search className="absolute right-3 top-1/2 size-5 -translate-y-1/2 text-[#99a2b3]" />
          <input
            className="h-11 w-full rounded-lg border border-[#dce1ea] px-4 text-base outline-none"
            placeholder="请输入素材名称"
          />
        </label>
        <button
          type="button"
          className="mb-4 h-11 w-full rounded-md border border-[#dce1ea] text-base font-semibold"
        >
          上传文本素材
        </button>
        <div className="grid grid-cols-2 gap-3">
          {materialItems.map((item) => (
            <div
              key={item.title}
              className="overflow-hidden rounded-lg border border-[#dce1ea] bg-[#f3f6fa]"
            >
              <div className="min-h-28 rounded-lg bg-white p-3 text-base leading-6 text-[#2e384a]">
                {item.text}
              </div>
              <div className="p-3">
                <div className="mb-2 flex items-center justify-between">
                  <strong className="text-base text-[#0f172a]">
                    {item.title}
                  </strong>
                  <span className="text-[#6f7890]">...</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-[#5c6472]">
                  <Users className="size-4 fill-[#5f58ff] text-[#5f58ff]" />
                  {item.author} {item.time}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AssistantPanel() {
  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="智能助手" />
      <div className="min-h-0 overflow-y-auto px-5 py-5">
        <section className="rounded-2xl bg-[#f3f6fa] p-5">
          <h3 className="text-xl font-semibold text-[#1f2a44]">
            AI对话助手设置
          </h3>
          <p className="mt-2 text-base text-[#374151]">
            智能生成专业话术，提升沟通效率与准确度
          </p>
          <div className="mt-5 rounded-xl bg-white p-4">
            <div className="flex items-center gap-3">
              <Avatar
                name="系统预设"
                tone="from-rose-300 to-slate-700"
                size="sm"
              />
              <div className="flex-1">
                <div className="text-lg font-medium text-[#1f2a44]">
                  系统预设
                </div>
                <div className="text-base text-[#475467]">系统预设</div>
              </div>
              <ChevronDown className="size-5 text-[#6b7280]" />
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between rounded-xl bg-white p-4 text-lg text-[#1f2a44]">
            <span className="flex items-center gap-2">
              实时智能推荐
              <CircleCheck className="size-5 text-[#6b7280]" />
            </span>
            <span className="flex h-8 w-14 items-center rounded-full bg-[#9ba3b7] p-1">
              <span className="size-6 rounded-full bg-white shadow" />
            </span>
          </div>
        </section>

        <section className="mt-6 rounded-2xl bg-[#f3f6fa] p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-semibold text-[#1f2a44]">
              AI客服助手设置
            </h3>
            <span className="flex h-8 w-14 items-center rounded-full bg-[#9ba3b7] p-1">
              <span className="size-6 rounded-full bg-white shadow" />
            </span>
          </div>
          <p className="mt-2 text-base text-[#374151]">
            AI助手将智能响应客户消息，下面为当前对接的智能体
          </p>
          <div className="mt-5 flex items-center gap-3 rounded-xl bg-white p-4">
            <Avatar name="小琪" tone="from-yellow-300 to-slate-800" size="sm" />
            <div className="flex-1">
              <div className="text-lg font-medium text-[#1f2a44]">
                SDR市场专员小琪
              </div>
              <div className="text-base text-[#475467]">新小琪</div>
            </div>
            <span className="rounded-md bg-[#e4f2ff] px-3 py-1.5 text-base text-[#2d79bd]">
              小懂智能体
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}

function HistoryPanel() {
  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="历史记录" />
      <div className="min-h-0 overflow-y-auto px-5 py-4">
        <div className="mb-6 w-fit border-b-4 border-[#5f58ff] pb-3 text-xl text-[#1f2a44]">
          联系记录
        </div>
        <div className="relative border-l-2 border-[#dce1ea] pl-6">
          <span className="absolute -left-[7px] top-1 size-3 rounded-full bg-[#9aa3b5]" />
          <div className="text-xl text-[#172033]">
            K12教辅企业咨询AI销售智能体
            <span className="mx-3 text-[#c3c8d2]">→</span>
            <span className="rounded-md bg-[#eeeaff] px-3 py-1 text-base text-[#5f58ff]">
              人工
            </span>
          </div>
          <p className="mt-4 text-lg leading-8 text-[#334155]">
            客户来自湖州云梯科技，从事K12教辅图书及课程销售，与学而思、新东方合作，咨询DearLink
            Plus销售智能体，用于提升线索筛选和转化效率。已提供姓名（褚总）和电话。
          </p>
          <div className="mt-4 flex items-center gap-2 text-lg text-[#6b7280]">
            <Clock className="size-5" />
            2026-06-04 17:47:34
          </div>
        </div>
      </div>
    </div>
  );
}

function RightContent({
  panel,
  conversation,
}: {
  panel: RightPanel;
  conversation: Conversation;
}) {
  if (panel === 'talk') return <TalkPanel />;
  if (panel === 'material') return <MaterialPanel />;
  if (panel === 'assistant') return <AssistantPanel />;
  if (panel === 'history') return <HistoryPanel />;
  return <CustomerInfoPanel conversation={conversation} />;
}

function ToolRail({
  activePanel,
  onChange,
}: {
  activePanel: RightPanel;
  onChange: (panel: RightPanel) => void;
}) {
  const tools: { label: string; panel: RightPanel; icon: typeof FileText }[] = [
    { label: '客户信息', panel: 'customer', icon: FileText },
    { label: '话术库', panel: 'talk', icon: Send },
    { label: '素材库', panel: 'material', icon: Archive },
    { label: '智能助手', panel: 'assistant', icon: MessageSquare },
    { label: '历史记录', panel: 'history', icon: History },
  ];

  return (
    <aside className="flex min-h-0 flex-col items-center border-l border-[#dde0e6] bg-white py-3">
      <div className="flex flex-1 flex-col items-center gap-4">
        {tools.map((tool) => (
          <button
            key={tool.panel}
            type="button"
            onClick={() => onChange(tool.panel)}
            className={cn(
              'flex w-full flex-col items-center gap-1 px-2 py-1.5 text-sm transition',
              activePanel === tool.panel ? 'text-[#5f58ff]' : 'text-[#8d95a6]',
            )}
          >
            <tool.icon className="size-6" />
            <span className="leading-5">{tool.label}</span>
          </button>
        ))}
      </div>
      <button
        type="button"
        className="mb-8 flex size-10 items-center justify-center rounded-full bg-[#5f58ff] text-white shadow-lg"
      >
        <Archive className="size-5" />
      </button>
      <div className="size-16 rounded-full bg-white p-1 shadow-[0_8px_24px_rgba(15,23,42,0.18)]">
        <Avatar name="珊珊" tone="from-rose-200 to-slate-700" size="lg" />
      </div>
    </aside>
  );
}

export default function SalesChatPage() {
  const defaultConversation =
    conversations.find((conversation) => conversation.active) ||
    conversations[0];
  const [selectedId, setSelectedId] = useState(defaultConversation.id);
  const [draft, setDraft] = useState('');
  const [aiReply, setAiReply] = useState(true);
  const [activePanel, setActivePanel] = useState<RightPanel>('customer');
  const [openFilter, setOpenFilter] = useState<FilterKey>(null);
  const [localMessages, setLocalMessages] = useState<
    Record<string, ChatMessage[]>
  >({});

  const selectedConversation = useMemo(
    () =>
      conversations.find((conversation) => conversation.id === selectedId) ||
      defaultConversation,
    [defaultConversation, selectedId],
  );

  const messages = useMemo(
    () => [
      ...(seedMessages[selectedConversation.id] || seedMessages.jiushi || []),
      ...(localMessages[selectedConversation.id] || []),
    ],
    [localMessages, selectedConversation.id],
  );

  function sendDraft() {
    const value = draft.trim();
    if (!value) return;
    setLocalMessages((current) => ({
      ...current,
      [selectedConversation.id]: [
        ...(current[selectedConversation.id] || []),
        {
          id: `${selectedConversation.id}-${Date.now()}`,
          author: 'sales-admin@local',
          time: '刚刚',
          role: 'agent',
          body: value,
        },
      ],
    }));
    setDraft('');
  }

  return (
    <div className="h-full min-h-0 overflow-hidden bg-[#eef0f3] text-[#1f2a44]">
      <div className="h-full min-h-0 overflow-x-auto">
        <div className="grid h-full min-w-[1520px] grid-rows-[68px_minmax(0,1fr)] rounded-lg border border-[#dde0e6] bg-white">
          <AppTopBar />
          <div className="grid min-h-0 grid-cols-[68px_388px_minmax(560px,1fr)_430px_76px]">
            <AppRail />
            <ConversationList
              selectedConversation={selectedConversation}
              openFilter={openFilter}
              onFilter={setOpenFilter}
              onSelect={setSelectedId}
            />
            <ChatCenter
              selectedConversation={selectedConversation}
              messages={messages}
              draft={draft}
              aiReply={aiReply}
              onDraft={setDraft}
              onSend={sendDraft}
              onToggleAI={() => setAiReply((current) => !current)}
            />
            <RightContent
              panel={activePanel}
              conversation={selectedConversation}
            />
            <ToolRail activePanel={activePanel} onChange={setActivePanel} />
          </div>
        </div>
      </div>
    </div>
  );
}
