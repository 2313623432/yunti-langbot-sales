import { useCallback, useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http';
import { ResourceIssue } from '../types/monitoring';
import { parseUTCTimestamp } from '../utils/dateUtils';

interface RawResourceIssue {
  id: number;
  session_id: string;
  bot_uuid: string;
  pipeline_uuid: string;
  target_type: string;
  target_id: string;
  platform: string;
  user_id: string;
  user_name: string;
  status: string;
  issue_type: string;
  book_id: string;
  merchant: string;
  question_location: string;
  issue_summary: string;
  user_description: string;
  evidence_images?: string[];
  internal_note: string;
  operator: string;
  resolution_note: string;
  completion_reply: string;
  created_at?: string;
  updated_at?: string;
  resolved_at?: string;
  replied_at?: string;
}

function toResourceIssue(item: RawResourceIssue): ResourceIssue {
  return {
    id: item.id,
    sessionId: item.session_id,
    botUuid: item.bot_uuid,
    pipelineUuid: item.pipeline_uuid,
    targetType: item.target_type,
    targetId: item.target_id,
    platform: item.platform,
    userId: item.user_id,
    userName: item.user_name,
    status: item.status as ResourceIssue['status'],
    issueType: item.issue_type,
    bookId: item.book_id,
    merchant: item.merchant,
    questionLocation: item.question_location,
    issueSummary: item.issue_summary,
    userDescription: item.user_description,
    evidenceImages: Array.isArray(item.evidence_images)
      ? item.evidence_images
      : [],
    internalNote: item.internal_note,
    operator: item.operator,
    resolutionNote: item.resolution_note,
    completionReply: item.completion_reply,
    createdAt: item.created_at ? parseUTCTimestamp(item.created_at) : undefined,
    updatedAt: item.updated_at ? parseUTCTimestamp(item.updated_at) : undefined,
    resolvedAt: item.resolved_at
      ? parseUTCTimestamp(item.resolved_at)
      : undefined,
    repliedAt: item.replied_at ? parseUTCTimestamp(item.replied_at) : undefined,
  };
}

export function useResourceIssueData() {
  const [issues, setIssues] = useState<ResourceIssue[]>([]);
  const [loading, setLoading] = useState(false);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const fetchIssues = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await httpClient.get<{ issues: RawResourceIssue[] }>(
        '/api/v1/sales/resource-issues',
      );
      setIssues((result?.issues || []).map(toResourceIssue));
    } catch (err) {
      setError(err as Error);
      console.error('Failed to fetch resource issues:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const resolveIssue = useCallback(
    async (issueId: number) => {
      setUpdatingId(issueId);
      try {
        await httpClient.post(`/api/v1/sales/resource-issues/${issueId}/resolve`, {
          reply_user: true,
        });
        await fetchIssues();
      } finally {
        setUpdatingId(null);
      }
    },
    [fetchIssues],
  );

  useEffect(() => {
    fetchIssues();
  }, [fetchIssues]);

  return {
    issues,
    loading,
    updatingId,
    error,
    refetch: fetchIssues,
    resolveIssue,
  };
}
