import React from 'react';
import { CheckCircle2, RefreshCw } from 'lucide-react';
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

export function ResourceIssuesTab({
  issues,
  loading,
  updatingId,
  onRefresh,
  onResolve,
}: ResourceIssuesTabProps) {
  if (loading) {
    return (
      <div className="py-12 flex justify-center">
        <LoadingSpinner text="正在加载资源问题" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-foreground">资源问题表</h3>
          <p className="text-sm text-muted-foreground">
            汇总扫码资源缺失、为空、上传中和内容错误问题。
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="w-4 h-4 mr-2" />
          刷新
        </Button>
      </div>

      {issues.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-muted-foreground py-16 gap-2 border rounded-xl">
          <CheckCircle2 className="h-12 w-12" />
          <div className="text-sm">暂无资源问题记录</div>
        </div>
      ) : (
        <div className="border rounded-xl overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[8rem]">状态</TableHead>
                <TableHead className="w-[8rem]">类型</TableHead>
                <TableHead>问题描述</TableHead>
                <TableHead className="w-[14rem]">书籍/商家</TableHead>
                <TableHead className="w-[14rem]">会话</TableHead>
                <TableHead className="w-[10rem] text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {issues.map((issue) => (
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
                  <TableCell>
                    {issueTypeLabels[issue.issueType] || issue.issueType}
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="font-medium text-sm">
                        {issue.issueSummary || issue.userDescription || '-'}
                      </div>
                      {issue.questionLocation && (
                        <div className="text-xs text-muted-foreground">
                          位置：{issue.questionLocation}
                        </div>
                      )}
                      {issue.evidenceImages.length > 0 && (
                        <div className="text-xs text-muted-foreground">
                          证据图片：{issue.evidenceImages.length} 张
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1 text-sm">
                      <div>{issue.bookId || '-'}</div>
                      <div className="text-xs text-muted-foreground">
                        {issue.merchant || '未填写商家'}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1 text-xs">
                      <div className="font-mono">{issue.sessionId}</div>
                      <div className="text-muted-foreground">
                        {issue.userName || issue.userId || issue.targetId}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {issue.status === 'open' || issue.status === 'reported' ? (
                      <Button
                        size="sm"
                        onClick={() => onResolve(issue.id)}
                        disabled={updatingId === issue.id}
                      >
                        <CheckCircle2 className="w-4 h-4 mr-2" />
                        {updatingId === issue.id ? '处理中' : '处理完并回访'}
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {issue.repliedAt
                          ? `已回访 ${issue.repliedAt.toLocaleString()}`
                          : '无需操作'}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
