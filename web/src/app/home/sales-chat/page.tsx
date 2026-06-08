import { useMemo, useState } from 'react';
import {
  Archive,
  AtSign,
  BriefcaseBusiness,
  CalendarDays,
  ChevronDown,
  CircleCheck,
  Clock,
  Eye,
  FileText,
  Funnel,
  History,
  ImageIcon,
  Megaphone,
  MessageSquare,
  PenLine,
  RotateCcw,
  Search,
  Send,
  SlidersHorizontal,
  Smile,
  Sparkles,
  SquarePen,
  Star,
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
type MainView = 'conversation' | 'customers' | 'workbench' | 'settings';
type AddressBookTab = 'friends' | 'groups';
type CustomerFieldValues = Record<string, string>;
type CheckedMap = Record<string, boolean>;

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

const customerStages = ['意向客户', '中性客户', '低意向', '已成交'];

type CustomerRow = {
  name: string;
  need: string;
  tags: string[];
  type: '意向客户' | '非意向客户' | '潜在客户';
  date: string;
  tone: string;
  dot: string;
};

const customerRows: CustomerRow[] = [
  {
    name: '郑雪',
    need: '我们专注用AI技术帮助企业提升销售效率，想了解一下你们的需求。',
    tags: [],
    type: '潜在客户',
    date: '2026-05-22 10:18',
    tone: 'from-sky-300 to-blue-600',
    dot: 'bg-[#6a63ff]',
  },
  {
    name: '阿曼达',
    need: '您好，我们的业务提供媒体门户、私域转化和销售自动化服务。',
    tags: ['公司名称:杭州韬画科技有限公司'],
    type: '意向客户',
    date: '2025-09-17 10:26',
    tone: 'from-lime-100 to-emerald-500',
    dot: 'bg-[#51b970]',
  },
  {
    name: '宫英',
    need: '好的，收到～请问怎么称呼您呢？',
    tags: ['公司名称:青岛银行', '客户称呼:宫老师'],
    type: '意向客户',
    date: '2026-03-16 14:39',
    tone: 'from-cyan-200 to-slate-600',
    dot: 'bg-[#51b970]',
  },
  {
    name: '云麟',
    need: '不是客户，属于合作伙伴',
    tags: ['合作伙伴', '联系方式:13302917964'],
    type: '非意向客户',
    date: '2026-01-28 15:43',
    tone: 'from-stone-900 to-yellow-700',
    dot: 'bg-[#e5a933]',
  },
  {
    name: '陈敏慧',
    need: '- DearLink Plus：更偏销售侧，能自动筛选线索并转人工。',
    tags: [],
    type: '潜在客户',
    date: '2026-05-15 16:01',
    tone: 'from-rose-200 to-orange-400',
    dot: 'bg-[#6a63ff]',
  },
  {
    name: 'Linette.Wu（吴雪莲）',
    need: '您这是自动回复吗',
    tags: ['公司名称：火星语盟AI事业部'],
    type: '非意向客户',
    date: '2026-02-27 11:52',
    tone: 'from-zinc-500 to-zinc-900',
    dot: 'bg-[#e5a933]',
  },
  {
    name: '李立中',
    need: '不能先看效果嘛，看完之后再决定',
    tags: ['用户基本信息（五邑大学图灵实验室、...）'],
    type: '意向客户',
    date: '2025-11-01 16:21',
    tone: 'from-sky-400 to-blue-700',
    dot: 'bg-[#51b970]',
  },
  {
    name: '张辉',
    need: '好的 多谢',
    tags: ['用户基本信息（公司名称：北京登时信）'],
    type: '非意向客户',
    date: '2026-03-06 10:16',
    tone: 'from-stone-200 to-stone-500',
    dot: 'bg-[#e5a933]',
  },
  {
    name: '龙丽君',
    need: '价格这块我没有权限直接提供呢',
    tags: ['禾禾融数科', '龙总', '13530713917'],
    type: '意向客户',
    date: '2026-03-06 18:41',
    tone: 'from-amber-100 to-amber-700',
    dot: 'bg-[#51b970]',
  },
  {
    name: '姜浩然',
    need: '我们专注用AI技术帮助企业提升获客效率。',
    tags: [],
    type: '潜在客户',
    date: '2026-03-10 14:06',
    tone: 'from-red-900 to-zinc-900',
    dot: 'bg-[#6a63ff]',
  },
];

const addressFriends = [
  { id: 'zhenglei', name: '郑雷', tone: 'from-sky-300 to-blue-600' },
  { id: 'amanda', name: '阿曼达', tone: 'from-lime-100 to-emerald-500' },
  { id: 'guan', name: '官英', tone: 'from-cyan-200 to-slate-600' },
  { id: 'yunlin', name: '云麟', tone: 'from-stone-900 to-yellow-700' },
  { id: 'chen', name: '陈敏慧', tone: 'from-rose-200 to-orange-400' },
  { id: 'linette', name: 'Linette.Wu（吴雪莲）', tone: 'from-zinc-500 to-zinc-900' },
  { id: 'lizhong', name: '李立中', tone: 'from-sky-400 to-blue-700' },
  { id: 'zhanghui', name: '张辉', tone: 'from-stone-200 to-stone-500' },
];

const addressGroups = [
  { id: 'k12-sales', name: 'K12教辅客户跟进群', tone: 'from-indigo-400 to-blue-600' },
  { id: 'ops', name: '私域运营转化群', tone: 'from-violet-300 to-indigo-600' },
  { id: 'service', name: '售后协作群', tone: 'from-emerald-300 to-teal-700' },
  { id: 'demo', name: '演示预约群', tone: 'from-amber-300 to-orange-600' },
];

function makeCustomerFieldValues(): CustomerFieldValues {
  return Object.fromEntries(
    baseFields.map((field) => [field.label, field.value]),
  );
}

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

function CheckBox({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      className={cn(
        'flex size-4 items-center justify-center rounded border transition',
        checked ? 'border-[#5f58ff] bg-[#5f58ff]' : 'border-[#d7dbe4] bg-white',
      )}
    >
      {checked && <span className="size-1.5 rounded-full bg-white" />}
    </button>
  );
}

function ToggleSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={cn(
        'flex h-8 w-14 items-center rounded-full p-1 transition',
        checked ? 'bg-[#5f62ff]' : 'bg-[#9ba3b7]',
      )}
    >
      <span
        className={cn(
          'size-6 rounded-full bg-white shadow transition',
          checked && 'translate-x-6',
        )}
      />
    </button>
  );
}

function AppRail({
  activeView,
  onViewChange,
}: {
  activeView: MainView;
  onViewChange: (view: MainView) => void;
}) {
  const items: { label: string; icon: typeof MessageSquare; view: MainView }[] =
    [
      { label: '对话', icon: MessageSquare, view: 'conversation' },
      { label: '客户', icon: Users, view: 'customers' },
      { label: '工作台', icon: BriefcaseBusiness, view: 'workbench' },
    ];

  return (
    <nav className="border-r border-[#dde0e6] bg-[#eef0f3] py-2">
      <div className="flex flex-col items-center gap-2">
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => onViewChange(item.view)}
            className={cn(
              'flex w-12 flex-col items-center gap-1 rounded-xl py-2 text-xs transition',
              activeView === item.view
                ? 'bg-[#e3e4ff] text-[#5a55ff]'
                : 'text-[#8e96a6]',
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
        'inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-sm text-[#283248] transition',
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
  selectedAccount,
  selectedType,
  checkedReplies,
  onAccountChange,
  onTypeChange,
  onReplyToggle,
}: {
  openFilter: Exclude<FilterKey, null>;
  selectedAccount: string;
  selectedType: string;
  checkedReplies: CheckedMap;
  onAccountChange: (value: string) => void;
  onTypeChange: (value: string) => void;
  onReplyToggle: (value: string) => void;
}) {
  if (openFilter === 'account') {
    return (
      <div className="absolute left-4 top-[116px] z-20 w-[286px] rounded-lg bg-white p-3 shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
        {['张小琪', '珊珊', '全部账号'].map((account) => (
          <button
            key={account}
            type="button"
            onClick={() => onAccountChange(account)}
            className="flex w-full items-center gap-3 rounded-md px-3 py-3 text-left text-sm text-[#374151] hover:bg-[#f7f8fb]"
          >
            <CheckBox
              checked={selectedAccount === account}
              onChange={() => onAccountChange(account)}
            />
            <Avatar
              name={account}
              tone="from-slate-600 to-slate-800"
              size="xs"
            />
            <span>{account}</span>
          </button>
        ))}
      </div>
    );
  }

  if (openFilter === 'type') {
    return (
      <div className="absolute left-[148px] top-[116px] z-20 w-28 rounded-lg bg-white py-2 text-base text-[#202a3c] shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
        {['私聊', '群聊'].map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => onTypeChange(type)}
            className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-[#f6f7fb]"
          >
            <CheckBox
              checked={selectedType === type}
              onChange={() => onTypeChange(type)}
            />
            {type}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="absolute left-[250px] top-[116px] z-20 w-36 rounded-lg bg-white p-3 text-base text-[#202a3c] shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
      {['AI回复', '人工回复', 'SDR进程中'].map((item) => (
        <label key={item} className="flex items-center gap-2 py-1.5">
          <CheckBox
            checked={checkedReplies[item] || false}
            onChange={() => onReplyToggle(item)}
          />
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
  selectedAccount,
  selectedType,
  checkedReplies,
  onFilter,
  onAccountChange,
  onTypeChange,
  onReplyToggle,
  onSelect,
  onAddFriend,
  onOpenAddressBook,
}: {
  selectedConversation: Conversation;
  openFilter: FilterKey;
  selectedAccount: string;
  selectedType: string;
  checkedReplies: CheckedMap;
  onFilter: (filter: FilterKey) => void;
  onAccountChange: (value: string) => void;
  onTypeChange: (value: string) => void;
  onReplyToggle: (value: string) => void;
  onSelect: (id: string) => void;
  onAddFriend: () => void;
  onOpenAddressBook: () => void;
}) {
  return (
    <aside className="relative min-h-0 border-r border-[#dde0e6] bg-white">
      <div className="flex h-16 items-center justify-between border-b border-[#eef0f3] px-5">
        <h1 className="text-xl font-semibold text-[#1f2a44]">对话</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onAddFriend}
            aria-label="加好友"
            className="rounded-xl border border-[#dbe0ea] p-2 text-[#8c93a3]"
          >
            <UserPlus className="size-5" />
          </button>
          <button
            type="button"
            onClick={onOpenAddressBook}
            aria-label="通讯录"
            className="rounded-xl border border-[#dbe0ea] p-2 text-[#8c93a3]"
          >
            <FileText className="size-5" />
          </button>
        </div>
      </div>

      <div className="space-y-4 px-4 py-4">
        <label className="relative block">
          <Search className="absolute right-3 top-1/2 size-5 -translate-y-1/2 text-[#9aa3b5]" />
          <input
            className="h-10 w-full rounded-lg border border-[#dce1ea] bg-white px-3 pr-10 text-sm outline-none placeholder:text-[#9aa3b5]"
            placeholder="搜索备注/昵称/群名"
          />
        </label>
        <div className="flex items-center justify-between gap-2">
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

      {openFilter && (
        <FilterPopover
          openFilter={openFilter}
          selectedAccount={selectedAccount}
          selectedType={selectedType}
          checkedReplies={checkedReplies}
          onAccountChange={onAccountChange}
          onTypeChange={onTypeChange}
          onReplyToggle={onReplyToggle}
        />
      )}

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
    <div className="flex gap-3 px-5">
      <Avatar
        name={message.author}
        tone={
          isAgent
            ? 'from-slate-600 to-slate-800'
            : 'from-slate-700 to-slate-400'
        }
        size="sm"
      />
      <div className="max-w-[min(560px,calc(100%-3rem))]">
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
    <div className="mx-auto w-[min(430px,calc(100%-2rem))] rounded-xl bg-white/70 px-5 py-5 shadow-sm">
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
  conversationClosed,
  onDraft,
  onSend,
  onToggleAI,
  onEndConversation,
  onRestoreConversation,
}: {
  selectedConversation: Conversation;
  messages: ChatMessage[];
  draft: string;
  aiReply: boolean;
  conversationClosed: boolean;
  onDraft: (value: string) => void;
  onSend: () => void;
  onToggleAI: () => void;
  onEndConversation: () => void;
  onRestoreConversation: () => void;
}) {
  return (
    <main className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)_216px] bg-[#dedee6]">
      <header className="flex items-center justify-between gap-3 border-b border-[#dde0e6] bg-white px-4">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate text-xl font-semibold text-[#1f2a44]">
            {selectedConversation.name}
          </h2>
          <SquarePen className="size-5 shrink-0 text-[#778198]" />
          <span className="shrink-0 text-base text-[#4b5568]">来源-微信</span>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <button
            type="button"
            onClick={onEndConversation}
            className={cn(
              'rounded p-1',
              conversationClosed ? 'text-[#5f58ff]' : 'text-[#8a93a6]',
            )}
          >
            <CircleCheck className="size-5" />
          </button>
          <button
            type="button"
            onClick={onRestoreConversation}
            className="rounded p-1 text-[#8a93a6] hover:bg-[#f4f6fa] hover:text-[#5f58ff]"
          >
            <RotateCcw className="size-5" />
          </button>
          <button
            type="button"
            onClick={onEndConversation}
            className={cn(
              'rounded-md border px-3 py-2 text-sm font-medium',
              conversationClosed
                ? 'border-[#cfd4df] text-[#8a93a6]'
                : 'border-[#625cff] text-[#5a55ff]',
            )}
          >
            {conversationClosed ? '已结束' : '结束对话'}
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

      <footer className="border-t border-[#dde0e6] bg-white px-4 py-3">
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

function PanelHeader({
  title,
  onClose,
}: {
  title: string;
  onClose: () => void;
}) {
  return (
    <div className="flex h-16 items-center justify-between border-b border-[#eef0f3] px-6">
      <h2 className="text-xl font-medium text-[#1f2a44]">{title}</h2>
      <button
        type="button"
        onClick={onClose}
        className="rounded-md p-1 text-[#8a8f9c] hover:bg-[#f4f6fa]"
      >
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

function CustomerInfoPanel({
  conversation,
  fields,
  editingField,
  customerStage,
  stageOpen,
  onClose,
  onFieldEdit,
  onFieldChange,
  onStageOpenChange,
  onStageChange,
}: {
  conversation: Conversation;
  fields: CustomerFieldValues;
  editingField: string | null;
  customerStage: string;
  stageOpen: boolean;
  onClose: () => void;
  onFieldEdit: (label: string | null) => void;
  onFieldChange: (label: string, value: string) => void;
  onStageOpenChange: (open: boolean) => void;
  onStageChange: (stage: string) => void;
}) {
  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="客户信息" onClose={onClose} />
      <div className="min-h-0 overflow-y-auto px-4 py-5">
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
              <div className="relative">
                <button
                  type="button"
                  onClick={() => onStageOpenChange(!stageOpen)}
                  className="flex items-center gap-1 rounded-md bg-[#f0efff] px-3 py-1.5 text-base text-[#5f58ff]"
                >
                  {customerStage}
                  <ChevronDown className="size-4" />
                </button>
                {stageOpen && (
                  <div className="absolute right-0 top-10 z-20 w-28 rounded-lg bg-white py-2 shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
                    {customerStages.map((stage) => (
                      <button
                        key={stage}
                        type="button"
                        onClick={() => onStageChange(stage)}
                        className={cn(
                          'block w-full px-3 py-2 text-left text-sm hover:bg-[#f6f7fb]',
                          customerStage === stage && 'text-[#5f58ff]',
                        )}
                      >
                        {stage}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <p className="mt-3 flex items-center gap-2 text-base text-[#7b8495]">
              所属账号
              <span className="size-2 rounded-full bg-[#34bf64]" />
              <span className="text-[#475467]">张小琪</span>
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
                className="grid grid-cols-[92px_1fr] items-center gap-3 text-sm"
              >
                <span className="text-[#7b8495]">{field.label}</span>
                <span className="flex min-w-0 items-center gap-2 text-[#4a5568]">
                  {editingField === field.label ? (
                    <input
                      autoFocus
                      value={fields[field.label] || ''}
                      onChange={(event) =>
                        onFieldChange(field.label, event.target.value)
                      }
                      onBlur={() => onFieldEdit(null)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') onFieldEdit(null);
                      }}
                      className="h-8 min-w-0 flex-1 rounded-md border border-[#dce1ea] px-2 text-base outline-none focus:border-[#5f58ff]"
                    />
                  ) : (
                    <span className="truncate">
                      {fields[field.label] || '暂无'}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => onFieldEdit(field.label)}
                    className="shrink-0 rounded p-1 text-[#9ba3b2] hover:bg-[#f4f6fa] hover:text-[#5f58ff]"
                  >
                    <PenLine className="size-4" />
                  </button>
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
      </div>
    </div>
  );
}

function TalkPanel({ onClose }: { onClose: () => void }) {
  const [activeLibrary, setActiveLibrary] = useState<'team' | 'personal'>(
    'team',
  );
  const [searchText, setSearchText] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<CheckedMap>({
    全部话术: true,
  });
  const groups = [
    ['全部话术', '2'],
    ['新客引导话术', '1'],
    ['老客复购营销话术', '1'],
    ['活动话术', '0'],
    ['情绪安抚话术', '0'],
  ];

  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="话术库" onClose={onClose} />
      <div className="min-h-0 overflow-y-auto px-4 py-4">
        <div className="mb-4 flex items-center border-b border-[#e4e8f0] text-lg">
          <button
            type="button"
            onClick={() => setActiveLibrary('team')}
            className={cn(
              'px-2 py-3',
              activeLibrary === 'team'
                ? 'border-b-2 border-[#5f58ff] text-[#5f58ff]'
                : 'text-[#0f172a]',
            )}
          >
            团队话术库
          </button>
          <button
            type="button"
            onClick={() => setActiveLibrary('personal')}
            className={cn(
              'px-8 py-3',
              activeLibrary === 'personal'
                ? 'border-b-2 border-[#5f58ff] text-[#5f58ff]'
                : 'text-[#0f172a]',
            )}
          >
            个人话术库
          </button>
          <SlidersHorizontal className="ml-auto size-5 text-[#8d95a6]" />
        </div>
        <label className="relative mb-4 block">
          <Search className="absolute right-3 top-1/2 size-5 -translate-y-1/2 text-[#99a2b3]" />
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            className="h-11 w-full rounded-lg border border-[#dce1ea] px-4 text-base outline-none"
            placeholder="搜索标题/内容"
          />
        </label>
        {groups.map(([title, count]) => (
          <section key={title} className="border-b border-[#eef0f3]">
            <button
              type="button"
              onClick={() =>
                setExpandedGroups((current) => ({
                  ...current,
                  [title]: !current[title],
                }))
              }
              className="w-full py-4 text-left text-xl text-[#1f2a44]"
            >
              <span className="mr-3 text-sm">
                {expandedGroups[title] ? '▼' : '▶'}
              </span>
              {title}（{count}）
            </button>
            {expandedGroups[title] && count !== '0' && (
              <div className="pb-4 pl-7 text-base leading-7 text-[#4b5568]">
                {searchText ? `搜索：${searchText}` : 'K12客户咨询开场白'}
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}

function MaterialPanel({ onClose }: { onClose: () => void }) {
  const [activeTab, setActiveTab] = useState('文本');
  const [searchText, setSearchText] = useState('');
  const [items, setItems] = useState(materialItems);

  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="素材库" onClose={onClose} />
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
          ].map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                'pb-3',
                activeTab === tab && 'border-b-2 border-[#111827]',
              )}
            >
              {tab}
            </button>
          ))}
        </div>
        <label className="relative mb-3 block">
          <Search className="absolute right-3 top-1/2 size-5 -translate-y-1/2 text-[#99a2b3]" />
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            className="h-11 w-full rounded-lg border border-[#dce1ea] px-4 text-base outline-none"
            placeholder="请输入素材名称"
          />
        </label>
        <button
          type="button"
          onClick={() =>
            setItems((current) => [
              {
                title: `${activeTab}_新增`,
                author: '张小琪',
                time: '刚刚',
                text: `新建${activeTab}素材，可继续编辑后用于回复客户。`,
              },
              ...current,
            ])
          }
          className="mb-4 h-11 w-full rounded-md border border-[#dce1ea] text-base font-semibold"
        >
          上传{activeTab}素材
        </button>
        <div className="grid grid-cols-2 gap-3">
          {items
            .filter(
              (item) =>
                !searchText ||
                item.title.includes(searchText) ||
                item.text.includes(searchText),
            )
            .map((item) => (
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
                    <button
                      type="button"
                      onClick={() =>
                        setItems((current) =>
                          current.filter((entry) => entry.title !== item.title),
                        )
                      }
                      className="text-[#6f7890] hover:text-[#ef5148]"
                    >
                      ...
                    </button>
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

function AssistantPanel({
  onClose,
  smartRecommend,
  customerAssistant,
  onSmartRecommendChange,
  onCustomerAssistantChange,
}: {
  onClose: () => void;
  smartRecommend: boolean;
  customerAssistant: boolean;
  onSmartRecommendChange: () => void;
  onCustomerAssistantChange: () => void;
}) {
  const [presetOpen, setPresetOpen] = useState(false);
  const [preset, setPreset] = useState('系统预设');

  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="智能助手" onClose={onClose} />
      <div className="min-h-0 overflow-y-auto px-5 py-5">
        <section className="rounded-2xl bg-[#f3f6fa] p-5">
          <h3 className="text-xl font-semibold text-[#1f2a44]">
            AI对话助手设置
          </h3>
          <p className="mt-2 text-base text-[#374151]">
            智能生成专业话术，提升沟通效率与准确度
          </p>
          <div className="mt-5 rounded-xl bg-white p-4">
            <button
              type="button"
              onClick={() => setPresetOpen((current) => !current)}
              className="flex w-full items-center gap-3 text-left"
            >
              <Avatar
                name={preset}
                tone="from-rose-300 to-slate-700"
                size="sm"
              />
              <div className="flex-1">
                <div className="text-lg font-medium text-[#1f2a44]">
                  {preset}
                </div>
                <div className="text-base text-[#475467]">{preset}</div>
              </div>
              <ChevronDown className="size-5 text-[#6b7280]" />
            </button>
            {presetOpen && (
              <div className="mt-3 rounded-lg border border-[#eef0f3] bg-white p-2">
                {['系统预设', '高转化销售', '温和跟进'].map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => {
                      setPreset(item);
                      setPresetOpen(false);
                    }}
                    className="block w-full rounded-md px-3 py-2 text-left text-base hover:bg-[#f4f6fa]"
                  >
                    {item}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="mt-3 flex items-center justify-between rounded-xl bg-white p-4 text-lg text-[#1f2a44]">
            <span className="flex items-center gap-2">
              实时智能推荐
              <CircleCheck className="size-5 text-[#6b7280]" />
            </span>
            <ToggleSwitch
              checked={smartRecommend}
              onChange={onSmartRecommendChange}
            />
          </div>
        </section>

        <section className="mt-6 rounded-2xl bg-[#f3f6fa] p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-semibold text-[#1f2a44]">
              AI客服助手设置
            </h3>
            <ToggleSwitch
              checked={customerAssistant}
              onChange={onCustomerAssistantChange}
            />
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

function HistoryPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="grid min-h-0 grid-rows-[64px_minmax(0,1fr)] bg-white">
      <PanelHeader title="历史记录" onClose={onClose} />
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
  fields,
  editingField,
  customerStage,
  stageOpen,
  smartRecommend,
  customerAssistant,
  onClose,
  onFieldEdit,
  onFieldChange,
  onStageOpenChange,
  onStageChange,
  onSmartRecommendChange,
  onCustomerAssistantChange,
}: {
  panel: RightPanel;
  conversation: Conversation;
  fields: CustomerFieldValues;
  editingField: string | null;
  customerStage: string;
  stageOpen: boolean;
  smartRecommend: boolean;
  customerAssistant: boolean;
  onClose: () => void;
  onFieldEdit: (label: string | null) => void;
  onFieldChange: (label: string, value: string) => void;
  onStageOpenChange: (open: boolean) => void;
  onStageChange: (stage: string) => void;
  onSmartRecommendChange: () => void;
  onCustomerAssistantChange: () => void;
}) {
  if (panel === 'talk') return <TalkPanel onClose={onClose} />;
  if (panel === 'material') return <MaterialPanel onClose={onClose} />;
  if (panel === 'assistant') {
    return (
      <AssistantPanel
        onClose={onClose}
        smartRecommend={smartRecommend}
        customerAssistant={customerAssistant}
        onSmartRecommendChange={onSmartRecommendChange}
        onCustomerAssistantChange={onCustomerAssistantChange}
      />
    );
  }
  if (panel === 'history') return <HistoryPanel onClose={onClose} />;
  return (
    <CustomerInfoPanel
      conversation={conversation}
      fields={fields}
      editingField={editingField}
      customerStage={customerStage}
      stageOpen={stageOpen}
      onClose={onClose}
      onFieldEdit={onFieldEdit}
      onFieldChange={onFieldChange}
      onStageOpenChange={onStageOpenChange}
      onStageChange={onStageChange}
    />
  );
}

function ToolRail({
  activePanel,
  panelOpen,
  onChange,
}: {
  activePanel: RightPanel;
  panelOpen: boolean;
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
      <div className="flex flex-1 flex-col items-center gap-2">
        {tools.map((tool) => (
          <button
            key={tool.panel}
            type="button"
            onClick={() => onChange(tool.panel)}
            className={cn(
              'flex w-full flex-col items-center gap-1 px-1 py-1.5 text-xs transition',
              panelOpen && activePanel === tool.panel
                ? 'text-[#5f58ff]'
                : 'text-[#8d95a6]',
            )}
          >
            <tool.icon className="size-5" />
            <span className="whitespace-nowrap leading-4">{tool.label}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function MiniSparkline({ color }: { color: string }) {
  return (
    <svg width="88" height="36" viewBox="0 0 88 36" aria-hidden="true">
      <polyline
        points="2,28 12,14 22,18 32,16 42,4 52,29 62,12 72,28 86,28"
        fill="none"
        stroke={color}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

function CustomerManagementView() {
  const [activeMenu, setActiveMenu] = useState('全部客户');
  const [query, setQuery] = useState('');
  const [favoriteNames, setFavoriteNames] = useState<CheckedMap>({});
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null);

  const menus = [
    { label: '全部客户', icon: Users },
    { label: '意向客户', icon: UserPlus },
    { label: '非意向客户', icon: UserPlus },
    { label: '潜在客户', icon: UserPlus },
  ];

  const filteredCustomers = customerRows.filter((customer) => {
    const matchesMenu =
      activeMenu === '全部客户' || customer.type === activeMenu;
    const matchesQuery =
      !query.trim() ||
      `${customer.name}${customer.need}${customer.tags.join('')}`
        .toLowerCase()
        .includes(query.trim().toLowerCase());
    return matchesMenu && matchesQuery;
  });

  return (
    <>
      <aside className="border-r border-[#e2e5ec] bg-white px-5 py-8">
        <h2 className="mb-7 text-xl font-semibold text-[#111827]">客户管理</h2>
        <div className="space-y-2">
          {menus.map((menu) => (
            <button
              key={menu.label}
              type="button"
              onClick={() => setActiveMenu(menu.label)}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left text-base transition',
                activeMenu === menu.label
                  ? 'bg-[#f0f0ff] text-[#5a55ff]'
                  : 'text-[#6b7280] hover:bg-[#f7f8fb]',
              )}
            >
              <menu.icon className="size-5" />
              {menu.label}
            </button>
          ))}
        </div>
      </aside>
      <main className="min-h-0 overflow-auto bg-white px-7 py-7">
        <div className="mb-8 flex items-start justify-between">
          <h1 className="text-xl font-semibold text-[#1f2a44]">
            {activeMenu}（
            {activeMenu === '全部客户' ? 640 : filteredCustomers.length}）
          </h1>
          <div className="relative flex items-center gap-3">
            <div className="flex h-12 w-[470px] items-center justify-between rounded-md border border-[#e4e7ef] px-4 text-[#a0a7b7]">
              <span>开始日期</span>
              <span>→</span>
              <span>结束日期</span>
              <CalendarDays className="size-5" />
            </div>
            <button
              type="button"
              onClick={() => setFilterOpen((current) => !current)}
              className={cn(
                'flex size-12 items-center justify-center rounded-md border border-[#e4e7ef] text-[#586174] transition',
                filterOpen && 'border-[#5f58ff] text-[#5f58ff]',
              )}
            >
              <Funnel className="size-6" />
            </button>
            {filterOpen && (
              <div className="absolute right-0 top-14 z-10 w-52 rounded-lg bg-white p-3 shadow-[0_8px_30px_rgba(15,23,42,0.18)]">
                {['按客户类型', '按所属账号', '按加好友时间'].map((item) => (
                  <button
                    key={item}
                    type="button"
                    className="block w-full rounded-md px-3 py-2 text-left text-sm text-[#475569] hover:bg-[#f7f8fb]"
                  >
                    {item}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <section className="overflow-hidden rounded-2xl border border-[#e0e4ec] bg-white">
          <div className="px-5 py-6">
            <div className="mb-9 flex items-start justify-between">
              <div>
                <div className="mb-8 text-lg text-[#283248]">客户筛选进度</div>
                <div className="flex gap-14">
                  <div>
                    <div className="text-[#5f58ff]">已完成筛选</div>
                    <div className="text-3xl font-semibold text-[#6c68ff]">
                      161
                    </div>
                  </div>
                  <div>
                    <div className="text-[#49ad6b]">意向客户</div>
                    <div className="text-3xl font-semibold text-[#49ad6b]">
                      131
                    </div>
                  </div>
                  <div>
                    <div className="text-[#9aa2b2]">潜在客户筛选中</div>
                    <div className="text-3xl font-semibold text-[#9aa2b2]">
                      378
                    </div>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-[#687086]">已完成</div>
                <div className="text-5xl font-semibold text-[#5f58ff]">25%</div>
              </div>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-[#edf0f5]">
              <div className="flex h-full w-[84%]">
                <div className="w-[28%] bg-[#6767ff]" />
                <div className="w-[22%] bg-[#53b86f]" />
                <div className="flex-1 bg-[#c6cbd5]" />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-5 border-t border-[#e0e4ec]">
            {[
              { label: '全部客户', value: '640', color: '#5f62ff' },
              { label: '意向客户', value: '131', color: '#ff7a30' },
              { label: '非意向客户', value: '30', color: '#58b973' },
              { label: '潜在客户', value: '479', color: '#7a36f0' },
              { label: '意向客户率', value: '81%', color: '#5f62ff' },
            ].map((item) => (
              <div
                key={item.label}
                className="flex h-28 items-center justify-between border-r border-[#e0e4ec] px-5 last:border-r-0"
              >
                <div>
                  <div className="mb-2 flex items-center gap-2 text-[#7c8496]">
                    <Users className="size-5 text-[#5f58ff]" />
                    {item.label}
                  </div>
                  <div className="text-3xl font-semibold">{item.value}</div>
                </div>
                <MiniSparkline color={item.color} />
              </div>
            ))}
          </div>
        </section>

        <div className="mt-5 flex items-center justify-between">
          <div className="flex h-10 w-[270px] items-center gap-2 rounded-md border border-[#e4e7ef] px-4 text-[#a0a7b7]">
            <Search className="size-5" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full bg-transparent outline-none"
              placeholder="搜索用户昵称/备注"
            />
          </div>
          <button
            type="button"
            className="flex h-10 items-center gap-2 rounded-md border border-[#e4e7ef] px-3 text-[#586174]"
          >
            <SlidersHorizontal className="size-5" />列
          </button>
        </div>

        <div className="mt-5 overflow-hidden rounded-lg">
          <table className="w-full table-fixed border-collapse text-left">
            <thead>
              <tr className="h-16 bg-[#f8f8fb] text-[#34415c]">
                <th className="w-[180px] px-5 font-semibold">客户</th>
                <th className="w-[360px] px-5 font-semibold">需求标签</th>
                <th className="w-[360px] px-5 font-semibold">画像标签</th>
                <th className="w-[180px] px-5 font-semibold">客户类型</th>
                <th className="w-[240px] px-5 font-semibold">所属账号</th>
                <th className="w-[180px] px-5 font-semibold">加好友时间</th>
                <th className="w-[120px] px-5 font-semibold">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredCustomers.map((customer) => (
                <tr
                  key={customer.name}
                  className={cn(
                    'h-[76px] border-b border-[#f0f2f6] text-[#465169]',
                    selectedCustomer === customer.name && 'bg-[#f3f5ff]',
                  )}
                >
                  <td className="px-5">
                    <div className="flex items-center gap-3">
                      <Avatar
                        name={customer.name}
                        tone={customer.tone}
                        size="sm"
                      />
                      {customer.name}
                    </div>
                  </td>
                  <td className="truncate px-5 text-[#8c94a8]">
                    <span className="rounded bg-[#f4f5ff] px-2 py-1">
                      {customer.need}
                    </span>
                  </td>
                  <td className="px-5">
                    {customer.tags.length === 0 ? (
                      <span className="text-[#98a0b3]">-</span>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {customer.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full bg-[#f2f1ff] px-3 py-1 text-[#5f58ff]"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-5">
                    <span className="inline-flex items-center gap-1 rounded-full border border-[#e0e4ec] px-3 py-1">
                      <span
                        className={cn('size-2 rounded-full', customer.dot)}
                      />
                      {customer.type}
                    </span>
                  </td>
                  <td className="px-5">
                    <div className="flex items-center gap-2">
                      <Avatar
                        name="张小琪"
                        tone="from-stone-800 to-stone-500"
                        size="xs"
                      />
                      张小琪
                    </div>
                  </td>
                  <td className="px-5">{customer.date}</td>
                  <td className="px-5">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedCustomer(customer.name)}
                        className="flex size-8 items-center justify-center rounded-md border border-[#e4e7ef] text-[#697287]"
                      >
                        <Eye className="size-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setFavoriteNames((current) => ({
                            ...current,
                            [customer.name]: !current[customer.name],
                          }))
                        }
                        className={cn(
                          'flex size-8 items-center justify-center rounded-md border border-[#e4e7ef]',
                          favoriteNames[customer.name]
                            ? 'text-[#5f58ff]'
                            : 'text-[#697287]',
                        )}
                      >
                        <Star className="size-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-8 flex items-center justify-end gap-6 text-[#5d667a]">
          <button type="button" className="text-[#c0c6d2]">
            ‹
          </button>
          {[1, 2, 3, 4, 5].map((page) => (
            <button
              key={page}
              type="button"
              className={cn(
                'flex size-10 items-center justify-center rounded-md',
                page === 1
                  ? 'border border-[#5f58ff] text-[#5f58ff]'
                  : 'text-[#4b5563]',
              )}
            >
              {page}
            </button>
          ))}
          <span>…</span>
          <span>64</span>
          <button type="button">›</button>
          <button
            type="button"
            className="rounded-md border border-[#e0e4ec] px-4 py-2"
          >
            10 条/页
          </button>
          <span>跳至</span>
          <input className="h-10 w-16 rounded-md border border-[#e0e4ec] px-2 outline-none" />
          <span>页</span>
        </div>
      </main>
    </>
  );
}

function WorkbenchView() {
  const [activeAction, setActiveAction] = useState('新建群聊');
  const actions = [
    {
      title: '新建群聊',
      desc: '选择本企业同事发起群聊',
      icon: UserPlus,
      tone: 'text-[#111827]',
    },
    {
      title: '群聊群发',
      desc: '向多个群聊同时发送消息',
      icon: Users,
      tone: 'text-[#111827]',
    },
    {
      title: '群公告',
      desc: '向群聊发布公告通知',
      icon: Megaphone,
      tone: 'text-[#f5a12b]',
    },
    {
      title: '私聊群发',
      desc: '向多个好友同时发送消息',
      icon: MessageSquare,
      tone: 'text-[#111827]',
    },
    {
      title: '发朋友圈',
      desc: '配置朋友圈发布任务',
      icon: ImageIcon,
      tone: 'text-[#111827]',
    },
  ];

  return (
    <main className="min-h-0 overflow-auto bg-[#edf2f8] px-5 py-6">
      <h1 className="mb-6 text-2xl font-semibold text-[#111827]">工作台</h1>
      <div className="grid w-[1180px] grid-cols-3 gap-5">
        {actions.map((action) => (
          <button
            key={action.title}
            type="button"
            onClick={() => setActiveAction(action.title)}
            className={cn(
              'flex h-[154px] items-center gap-9 rounded-3xl border bg-white px-11 text-left transition',
              activeAction === action.title
                ? 'border-[#cfd5e3] shadow-sm'
                : 'border-[#d8deea]',
            )}
          >
            <action.icon className={cn('size-9 shrink-0', action.tone)} />
            <div>
              <div className="mb-4 text-xl font-semibold text-[#111827]">
                {action.title}
              </div>
              <div className="text-base text-[#8b94a7]">{action.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </main>
  );
}

function AddressBookModal({ onClose }: { onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<AddressBookTab>('friends');
  const [query, setQuery] = useState('');
  const list = activeTab === 'friends' ? addressFriends : addressGroups;
  const filteredList = list.filter((item) =>
    item.name.toLowerCase().includes(query.trim().toLowerCase()),
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-6 py-8">
      <div className="grid h-[min(760px,calc(100vh-80px))] w-[min(1080px,calc(100vw-80px))] grid-cols-[240px_minmax(0,1fr)] overflow-hidden rounded-2xl bg-white shadow-2xl">
        <aside className="border-r border-[#e5e8ef] px-4 py-8">
          <h2 className="mb-8 px-2 text-xl font-semibold text-[#111827]">
            通讯录
          </h2>
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-lg bg-[#f3f5fb] px-3 py-3 text-left"
          >
            <Avatar name="张小琪" tone="from-stone-800 to-stone-500" size="sm" />
            <span className="truncate text-sm font-medium text-[#1f2a44]">
              张小琪 @独到科技
            </span>
          </button>
        </aside>

        <section className="flex min-h-0 flex-col">
          <header className="flex h-20 items-center justify-between border-b border-[#eef0f3] px-7">
            <div className="flex h-full items-end gap-8">
              {[
                ['friends', '好友'],
                ['groups', '群聊'],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setActiveTab(value as AddressBookTab)}
                  className={cn(
                    'h-12 border-b-4 px-0 text-base font-semibold transition',
                    activeTab === value
                      ? 'border-[#5f58ff] text-[#1f2a44]'
                      : 'border-transparent text-[#4b5568]',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-4">
              <label className="relative block">
                <Search className="absolute right-3 top-1/2 size-5 -translate-y-1/2 text-[#9aa3b5]" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="h-10 w-[260px] rounded-lg border border-[#dce1ea] px-4 pr-10 text-sm outline-none placeholder:text-[#a0a7b7]"
                  placeholder="搜索备注/昵称/群名"
                />
              </label>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md p-1 text-[#111827] hover:bg-[#f4f6fa]"
              >
                <X className="size-5" />
              </button>
            </div>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-7 py-5">
            <div className="space-y-3">
              {filteredList.map((item) => (
                <div
                  key={item.id}
                  className="flex h-[68px] items-center justify-between rounded-xl border border-[#eef0f3] bg-white px-5 transition hover:bg-[#f8f9fc]"
                >
                  <div className="flex min-w-0 items-center gap-4">
                    <Avatar name={item.name} tone={item.tone} size="sm" />
                    <span className="truncate text-base font-medium text-[#374151]">
                      {item.name}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={onClose}
                    className="shrink-0 text-base font-medium text-[#5f58ff]"
                  >
                    发送消息
                  </button>
                </div>
              ))}
              {!filteredList.length && (
                <div className="rounded-xl border border-dashed border-[#dce1ea] py-12 text-center text-[#8b94a7]">
                  没有找到匹配的联系人
                </div>
              )}
            </div>
          </div>

          <footer className="flex h-16 items-center justify-between border-t border-[#eef0f3] px-7 text-sm text-[#5d667a]">
            <span>
              第 1 页，共 {activeTab === 'friends' ? 640 : addressGroups.length} 条
            </span>
            <div className="flex items-center gap-3">
              <button type="button" className="text-[#c0c6d2]">
                ‹
              </button>
              {[1, 2, 3].map((page) => (
                <button
                  key={page}
                  type="button"
                  className={cn(
                    'flex size-9 items-center justify-center rounded-md border',
                    page === 1
                      ? 'border-[#5f58ff] bg-[#f7f7ff] text-[#5f58ff]'
                      : 'border-[#e2e6ef] text-[#4b5563]',
                  )}
                >
                  {page}
                </button>
              ))}
              <span>…</span>
              <button
                type="button"
                className="flex size-9 items-center justify-center rounded-md border border-[#e2e6ef]"
              >
                32
              </button>
              <button type="button">›</button>
              <button
                type="button"
                className="inline-flex h-9 items-center gap-2 rounded-md border border-[#e2e6ef] px-3"
              >
                20条/页
                <ChevronDown className="size-4" />
              </button>
            </div>
          </footer>
        </section>
      </div>
    </div>
  );
}

function AddFriendModal({ onClose }: { onClose: () => void }) {
  const [accountOpen, setAccountOpen] = useState(false);
  const [account, setAccount] = useState('张小琪');
  const [phone, setPhone] = useState('');
  const [message, setMessage] = useState(
    '我是独到科技的张小琪，添加我的企业微信与我联系吧。',
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-6 py-8">
      <div className="w-[520px] rounded-lg bg-white p-8 shadow-2xl">
        <div className="mb-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-[#8a8f9c] hover:bg-[#f4f6fa]"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="relative mb-6">
          <button
            type="button"
            onClick={() => setAccountOpen((current) => !current)}
            className="flex h-16 w-full items-center justify-between rounded-xl border border-[#dce1ea] px-5 text-left shadow-sm"
          >
            <span className="text-base font-semibold text-[#6b7280]">
              加好友账号：
            </span>
            <span className="ml-auto mr-3 flex items-center gap-2 text-base font-semibold text-[#1f2937]">
              <span className="size-2 rounded-full bg-[#51b970]" />
              {account}
            </span>
            <ChevronDown className="size-5 text-[#9aa3b5]" />
          </button>
          {accountOpen && (
            <div className="absolute left-0 top-[72px] z-10 w-full rounded-lg border border-[#e5e8ef] bg-white p-2 shadow-xl">
              {['张小琪', '珊珊', '小琪'].map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setAccount(item);
                    setAccountOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-[#f7f8fb]"
                >
                  <span className="size-2 rounded-full bg-[#51b970]" />
                  {item}
                </button>
              ))}
            </div>
          )}
        </div>

        <label className="relative mb-6 block">
          <Search className="absolute left-4 top-1/2 size-5 -translate-y-1/2 text-[#9aa3b5]" />
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className="h-11 w-full rounded-md border border-[#dce1ea] px-12 text-base outline-none placeholder:text-[#a0a7b7]"
            placeholder="请输入手机号"
          />
        </label>

        <label className="block">
          <div className="mb-3 text-base font-semibold text-[#374151]">
            发送提醒：
          </div>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value.slice(0, 100))}
            className="h-44 w-full resize-none rounded-md border border-[#b7b9ff] px-5 py-4 text-base leading-7 text-[#374151] outline-none focus:border-[#5f58ff]"
          />
          <div className="mt-1 text-right text-sm text-[#9aa3b5]">
            {message.length} / 100
          </div>
        </label>

        <div className="mt-10 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="h-10 rounded-md border border-[#dce1ea] px-5 text-base text-[#374151]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onClose}
            className="h-10 rounded-md bg-[#5f58ff] px-5 text-base font-medium text-white disabled:bg-[#c5c8d6]"
            disabled={!phone.trim()}
          >
            发送申请
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SalesChatPage() {
  const defaultConversation =
    conversations.find((conversation) => conversation.active) ||
    conversations[0];
  const [mainView, setMainView] = useState<MainView>('conversation');
  const [selectedId, setSelectedId] = useState(defaultConversation.id);
  const [draft, setDraft] = useState('');
  const [aiReply, setAiReply] = useState(true);
  const [activePanel, setActivePanel] = useState<RightPanel>('customer');
  const [panelOpen, setPanelOpen] = useState(true);
  const [openFilter, setOpenFilter] = useState<FilterKey>(null);
  const [selectedAccount, setSelectedAccount] = useState('张小琪');
  const [selectedType, setSelectedType] = useState('私聊');
  const [checkedReplies, setCheckedReplies] = useState<CheckedMap>({
    AI回复: true,
    人工回复: true,
    SDR进程中: false,
  });
  const [customerFields, setCustomerFields] = useState<CustomerFieldValues>(
    makeCustomerFieldValues,
  );
  const [editingField, setEditingField] = useState<string | null>(null);
  const [customerStage, setCustomerStage] = useState('意向客户');
  const [stageOpen, setStageOpen] = useState(false);
  const [smartRecommend, setSmartRecommend] = useState(false);
  const [customerAssistant, setCustomerAssistant] = useState(false);
  const [conversationClosed, setConversationClosed] = useState(false);
  const [addressBookOpen, setAddressBookOpen] = useState(false);
  const [addFriendOpen, setAddFriendOpen] = useState(false);
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
    if (!value || conversationClosed) return;
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

  function openRightPanel(panel: RightPanel) {
    setActivePanel(panel);
    setPanelOpen(true);
  }

  function toggleReplyFilter(value: string) {
    setCheckedReplies((current) => ({
      ...current,
      [value]: !current[value],
    }));
  }

  if (mainView === 'customers') {
    return (
      <div className="h-full min-h-0 overflow-hidden bg-[#eef0f3] text-[#1f2a44]">
        <div className="h-full min-h-0 overflow-x-auto">
          <div className="h-full min-w-[1520px] rounded-lg border border-[#dde0e6] bg-white">
            <div className="grid h-full min-h-0 grid-cols-[68px_280px_minmax(1020px,1fr)]">
              <AppRail activeView={mainView} onViewChange={setMainView} />
              <CustomerManagementView />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (mainView === 'workbench') {
    return (
      <div className="h-full min-h-0 overflow-hidden bg-[#eef0f3] text-[#1f2a44]">
        <div className="h-full min-h-0 overflow-x-auto">
          <div className="h-full min-w-[1520px] rounded-lg border border-[#dde0e6] bg-white">
            <div className="grid h-full min-h-0 grid-cols-[68px_minmax(1200px,1fr)]">
              <AppRail activeView={mainView} onViewChange={setMainView} />
              <WorkbenchView />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 overflow-hidden bg-[#eef0f3] text-[#1f2a44]">
      <div className="h-full min-h-0 overflow-hidden">
        <div className="h-full min-w-0 rounded-lg border border-[#dde0e6] bg-white">
          <div
            className={cn(
              'grid h-full min-h-0',
              panelOpen
                ? 'grid-cols-[60px_minmax(260px,300px)_minmax(320px,1fr)_minmax(270px,340px)_64px] 2xl:grid-cols-[60px_340px_minmax(420px,1fr)_360px_64px]'
                : 'grid-cols-[60px_minmax(260px,300px)_minmax(320px,1fr)_64px] 2xl:grid-cols-[60px_340px_minmax(420px,1fr)_64px]',
            )}
          >
            <AppRail activeView={mainView} onViewChange={setMainView} />
            <ConversationList
              selectedConversation={selectedConversation}
              openFilter={openFilter}
              selectedAccount={selectedAccount}
              selectedType={selectedType}
              checkedReplies={checkedReplies}
              onFilter={setOpenFilter}
              onAccountChange={setSelectedAccount}
              onTypeChange={setSelectedType}
              onReplyToggle={toggleReplyFilter}
              onSelect={setSelectedId}
              onAddFriend={() => setAddFriendOpen(true)}
              onOpenAddressBook={() => setAddressBookOpen(true)}
            />
            <ChatCenter
              selectedConversation={selectedConversation}
              messages={messages}
              draft={draft}
              aiReply={aiReply}
              conversationClosed={conversationClosed}
              onDraft={setDraft}
              onSend={sendDraft}
              onToggleAI={() => setAiReply((current) => !current)}
              onEndConversation={() => setConversationClosed(true)}
              onRestoreConversation={() => setConversationClosed(false)}
            />
            {panelOpen && (
              <RightContent
                panel={activePanel}
                conversation={selectedConversation}
                fields={customerFields}
                editingField={editingField}
                customerStage={customerStage}
                stageOpen={stageOpen}
                smartRecommend={smartRecommend}
                customerAssistant={customerAssistant}
                onClose={() => setPanelOpen(false)}
                onFieldEdit={setEditingField}
                onFieldChange={(label, value) =>
                  setCustomerFields((current) => ({
                    ...current,
                    [label]: value,
                  }))
                }
                onStageOpenChange={setStageOpen}
                onStageChange={(stage) => {
                  setCustomerStage(stage);
                  setStageOpen(false);
                }}
                onSmartRecommendChange={() =>
                  setSmartRecommend((current) => !current)
                }
                onCustomerAssistantChange={() =>
                  setCustomerAssistant((current) => !current)
                }
              />
            )}
            <ToolRail
              activePanel={activePanel}
              panelOpen={panelOpen}
              onChange={openRightPanel}
            />
          </div>
        </div>
      </div>
      {addressBookOpen && (
        <AddressBookModal onClose={() => setAddressBookOpen(false)} />
      )}
      {addFriendOpen && (
        <AddFriendModal onClose={() => setAddFriendOpen(false)} />
      )}
    </div>
  );
}
