import React from 'react';
import { CheckCircle2, ExternalLink, Image as ImageIcon, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ResourceIssue } from '../types/monitoring';

interface ResourceIssuesTabProps {
  issues: ResourceIssue[];
  loading?: boolean;
  updatingId?: number | null;
  onRefresh: () => void;
  onResolve: (issueId: number) => void;
}

const issueTypeLabels: Record<string, string> = {
  missing_resource: '资源缺失',
  resource_uploading: '正在上传',
  empty_resource: '资源为空',
  content_error: '内容错误',
  resource_error: '资源异常',
};

const statusLabels: Record<string, string> = {
  open: '待处理',
  reported: '已反馈',
  resolved: '已解决',
  replied: '已回访',
  closed: '已关闭',
};

const statusClassNames: Record<string, string> = {
  open: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100',
  reported: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100',
  resolved:
    'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100',
  replied:
    'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100',
  closed: 'bg-muted text-muted-foreground',
};

function conversationHref(issue: ResourceIssue) {
  return `/home/sales-chat?session_id=${encodeURIComponent(issue.sessionId)}&handoff=1`;
}

function imageSrc(value: string) {
  if (!value || value.startsWith('http') || value.startsWith('data:')) return value;
  if (value.startsWith('/')) return value;
  return '';
}

export function ResourceIssuesTab({
  issues,
  loading,
  updatingId,
  onRefresh,
  onResolve,
}: ResourceIssuesTabProps) {
  const openIssues = issues.filter((issue) => issue.status !== 'resolved' && issue.status !== 'replied' && issue.status !== 'closed');
  const resolvedIssues = issues.filter((issue) => issue.status === 'resolved' || issue.status === 'replied' || issue.status === 'closed');

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner text="正在加载资源问题" />
      </div>
    );
  }

  function renderRows(items: ResourceIssue[], resolved: boolean) {
    return items.map((issue) => (
      <TableRow key={issue.id}>
        <TableCell>
          <Badge
            className={
              statusClassNames[issue.status] ||
              'bg-muted text-muted-foreground'
            }
          >
            {statusLabels[issue.status] || issue.status}
          </Badge>
        </TableCell>
        <TableCell>{issueTypeLabels[issue.issueType] || issue.issueType}</TableCell>
        <TableCell>
          <div className="space-y-1">
            <div className="text-sm font-medium">
              {issue.issueSummary || issue.userDescription || '-'}
            </div>
            {issue.userDescription && issue.userDescription !== issue.issueSummary && (
              <div className="whitespace-pre-wrap text-xs leading-5 text-muted-foreground">
                {issue.userDescription}
              </div>
            )}
            {issue.questionLocation && (
              <div className="text-xs text-muted-foreground">
                位置：{issue.questionLocation}
              </div>
            )}
          </div>
        </TableCell>
        <TableCell>
          <div className="space-y-1 text-sm">
            <div>{issue.userName || issue.userId || issue.targetId || '-'}</div>
            <div className="text-xs text-muted-foreground">{issue.platform || issue.targetType}</div>
          </div>
        </TableCell>
        <TableCell>
          {issue.evidenceImages.length ? (
            <div className="flex max-w-[18rem] flex-wrap gap-2">
              {issue.evidenceImages.map((image, index) => {
                const src = imageSrc(image);
                return src ? (
                  <a
                    key={`${image}-${index}`}
                    href={src}
                    target="_blank"
                    rel="noreferrer"
                    className="block h-14 w-14 overflow-hidden rounded-md border bg-muted"
                    title="查看照片"
                  >
                    <img src={src} alt="相关照片" className="h-full w-full object-cover" />
                  </a>
                ) : (
                  <div
                    key={`${image}-${index}`}
                    className="flex h-14 w-14 items-center justify-center rounded-md border bg-muted text-muted-foreground"
                    title={image}
                  >
                    <ImageIcon className="h-5 w-5" />
                  </div>
                );
              })}
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">暂无照片</span>
          )}
        </TableCell>
        <TableCell className="text-right">
          <div className="flex justify-end gap-2">
            <Button asChild size="sm" variant="outline">
              <a href={conversationHref(issue)}>
                <ExternalLink className="mr-2 h-4 w-4" />
                查看对话
              </a>
            </Button>
            {!resolved && (
              <Button
                size="sm"
                onClick={() => onResolve(issue.id)}
                disabled={updatingId === issue.id}
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                {updatingId === issue.id ? '处理中' : '已解决'}
              </Button>
            )}
          </div>
        </TableCell>
      </TableRow>
    ));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-foreground">资源问题表</h3>
          <p className="text-sm text-muted-foreground">
            汇总扫码资源缺失、为空、上传中和内容错误问题。
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          刷新
        </Button>
      </div>

      {issues.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border py-16 text-muted-foreground">
          <CheckCircle2 className="h-12 w-12" />
          <div className="text-sm">暂无资源问题记录</div>
        </div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[7rem]">状态</TableHead>
                  <TableHead className="w-[7rem]">类型</TableHead>
                  <TableHead>问题描述</TableHead>
                  <TableHead className="w-[12rem]">用户名称</TableHead>
                  <TableHead className="w-[20rem]">相关照片</TableHead>
                  <TableHead className="w-[14rem] text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>{renderRows(openIssues, false)}</TableBody>
            </Table>
          </div>

          <div className="space-y-3">
            <div>
              <h4 className="text-base font-semibold text-foreground">已解决问题表</h4>
              <p className="text-sm text-muted-foreground">点击已解决后会流转到这里。</p>
            </div>
            <div className="overflow-hidden rounded-xl border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[7rem]">状态</TableHead>
                    <TableHead className="w-[7rem]">类型</TableHead>
                    <TableHead>问题描述</TableHead>
                    <TableHead className="w-[12rem]">用户名称</TableHead>
                    <TableHead className="w-[20rem]">相关照片</TableHead>
                    <TableHead className="w-[14rem] text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {resolvedIssues.length ? (
                    renderRows(resolvedIssues, true)
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                        暂无已解决问题
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
