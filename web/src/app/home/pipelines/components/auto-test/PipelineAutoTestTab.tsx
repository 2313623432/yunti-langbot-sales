import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  Bot,
  CheckCircle2,
  FileText,
  History,
  Loader2,
  MessageSquareText,
  Play,
  RefreshCw,
  RotateCcw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Upload,
  Workflow,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  AutoTestMessage,
  AutoTestRun,
  AutoTestTarget,
  AutoTestTargetType,
} from '@/app/infra/entities/api';

interface PipelineAutoTestTabProps {
  initialTargetType?: AutoTestTargetType;
  initialTargetUuid?: string;
}

interface OptimizationPatchDetail {
  operation?: string;
  ai_generated?: boolean;
  model_name?: string;
  model_uuid?: string;
  reverted_at?: string;
  version_retention?: number;
  applied_patches?: Array<{
    path?: string;
    before?: unknown;
    after?: unknown;
  }>;
  ignored_patches?: Array<{
    path?: string;
    reason?: string;
  }>;
}

function errorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'msg' in error) {
    return String((error as { msg?: string }).msg || '操作失败');
  }
  return error instanceof Error ? error.message : '操作失败';
}

function formatTime(value?: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function renderMessageContent(message: AutoTestMessage) {
  if (message.content_type === 'image') {
    return (
      <img
        src={message.content}
        alt="测试图片消息"
        className="max-h-56 rounded-md border border-slate-200 object-contain"
      />
    );
  }
  if (message.content_type === 'voice') {
    return (
      <audio controls src={message.content} className="h-9 w-full max-w-sm">
        语音消息
      </audio>
    );
  }
  return <span className="whitespace-pre-wrap break-words">{message.content}</span>;
}

export default function PipelineAutoTestTab({
  initialTargetType = 'pipeline',
  initialTargetUuid = '',
}: PipelineAutoTestTabProps) {
  const [targetType, setTargetType] =
    useState<AutoTestTargetType>(initialTargetType);
  const [targetUuid, setTargetUuid] = useState(initialTargetUuid);
  const [targets, setTargets] = useState<{
    pipelines: AutoTestTarget[];
    workflows: AutoTestTarget[];
  }>({ pipelines: [], workflows: [] });
  const [runs, setRuns] = useState<AutoTestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AutoTestRun | null>(null);
  const [scenario, setScenario] = useState('');
  const [sopText, setSopText] = useState('');
  const [sopFilename, setSopFilename] = useState('');
  const [feedback, setFeedback] = useState<'satisfied' | 'unsatisfied'>(
    'satisfied',
  );
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reverting, setReverting] = useState(false);

  const targetOptions = useMemo(
    () => (targetType === 'pipeline' ? targets.pipelines : targets.workflows),
    [targetType, targets.pipelines, targets.workflows],
  );

  const selectedTarget = useMemo(
    () => targetOptions.find((item) => item.uuid === targetUuid) || null,
    [targetOptions, targetUuid],
  );

  const optimizationPatch = useMemo<OptimizationPatchDetail>(() => {
    const patch = selectedRun?.optimization_patch;
    return patch && typeof patch === 'object'
      ? (patch as OptimizationPatchDetail)
      : {};
  }, [selectedRun]);

  const appliedPatches = useMemo(
    () =>
      Array.isArray(optimizationPatch.applied_patches)
        ? optimizationPatch.applied_patches.filter((item) => item.path)
        : [],
    [optimizationPatch],
  );

  const loadTargets = useCallback(async () => {
    setLoading(true);
    try {
      const data = await httpClient.getAutoTestTargets();
      setTargets(data);
    } catch (error) {
      toast.error(`自动测试目标加载失败：${errorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRuns = useCallback(async () => {
    if (!targetUuid) return;
    setLoadingRuns(true);
    try {
      const data = await httpClient.getAutoTestRuns({
        target_type: targetType,
        target_uuid: targetUuid,
        limit: 30,
      });
      setRuns(data.runs);
      setSelectedRun((current) => current || data.runs[0] || null);
    } catch (error) {
      toast.error(`测试记录加载失败：${errorMessage(error)}`);
    } finally {
      setLoadingRuns(false);
    }
  }, [targetType, targetUuid]);

  useEffect(() => {
    loadTargets();
  }, [loadTargets]);

  useEffect(() => {
    if (targetOptions.length === 0) return;
    if (!targetOptions.some((item) => item.uuid === targetUuid)) {
      setTargetUuid(targetOptions[0].uuid);
    }
  }, [targetOptions, targetUuid]);

  useEffect(() => {
    setSelectedRun(null);
    loadRuns();
  }, [loadRuns]);

  async function handleSopFileChange(file?: File) {
    if (!file) return;
    const text = await file.text();
    setSopText(text);
    setSopFilename(file.name);
    toast.success('SOP 已读取，将用于自动测试调优');
  }

  async function handleStartRun() {
    if (!targetUuid) {
      toast.error('请先选择测试目标');
      return;
    }
    setStarting(true);
    try {
      const result = await httpClient.startAutoTestRun({
        target_type: targetType,
        target_uuid: targetUuid,
        scenario,
        turns: 3,
        sop_text: sopText,
        sop_filename: sopFilename,
      });
      setRuns((items) => [result.run, ...items]);
      setSelectedRun(result.run);
      setFeedback('satisfied');
      setReason('');
      toast.success('自动测试已完成');
    } catch (error) {
      toast.error(`自动测试失败：${errorMessage(error)}`);
    } finally {
      setStarting(false);
    }
  }

  async function handleSubmitFeedback() {
    if (!selectedRun) return;
    if (feedback === 'unsatisfied' && !reason.trim()) {
      toast.error('选择不满意时必须填写原因');
      return;
    }
    setSubmitting(true);
    try {
      const result = await httpClient.submitAutoTestFeedback(selectedRun.uuid, {
        feedback,
        reason: reason.trim(),
      });
      setSelectedRun(result.run);
      setRuns((items) =>
        items.map((item) => (item.uuid === result.run.uuid ? result.run : item)),
      );
      toast.success(feedback === 'satisfied' ? '反馈已记录' : '已生成并写入优化建议');
    } catch (error) {
      toast.error(`反馈提交失败：${errorMessage(error)}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevertOptimization() {
    if (!selectedRun || optimizationPatch.reverted_at) return;
    setReverting(true);
    try {
      const result = await httpClient.revertAutoTestRunOptimization(
        selectedRun.uuid,
      );
      setSelectedRun(result.run);
      setRuns((items) =>
        items.map((item) => (item.uuid === result.run.uuid ? result.run : item)),
      );
      toast.success('已撤销本次自动优化');
    } catch (error) {
      toast.error(`撤销失败：${errorMessage(error)}`);
    } finally {
      setReverting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner text="正在加载自动测试" />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-950">
            <Sparkles className="size-5 text-cyan-600" />
            自动测试
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            AI 模拟客户与客服对话，记录结果并根据人工反馈追加优化建议
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="h-9 rounded-lg"
            onClick={loadRuns}
            disabled={loadingRuns}
          >
            <RefreshCw
              className={`mr-1.5 size-4 ${loadingRuns ? 'animate-spin' : ''}`}
            />
            刷新
          </Button>
          <Button
            type="button"
            className="h-9 rounded-lg bg-cyan-700 px-4 hover:bg-cyan-800"
            onClick={handleStartRun}
            disabled={starting || !targetUuid}
          >
            {starting ? (
              <Loader2 className="mr-1.5 size-4 animate-spin" />
            ) : (
              <Play className="mr-1.5 size-4" />
            )}
            启动测试
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)_320px] gap-4 max-xl:grid-cols-1">
        <aside className="flex min-h-0 flex-col gap-4 overflow-hidden rounded-lg border border-slate-200 bg-white p-4">
          <div className="grid grid-cols-2 rounded-lg border border-slate-200 bg-slate-50 p-1">
            <Button
              type="button"
              variant={targetType === 'pipeline' ? 'default' : 'ghost'}
              className="h-8 rounded-md"
              onClick={() => setTargetType('pipeline')}
            >
              <Bot className="mr-1.5 size-4" />
              数字员工
            </Button>
            <Button
              type="button"
              variant={targetType === 'workflow' ? 'default' : 'ghost'}
              className="h-8 rounded-md"
              onClick={() => setTargetType('workflow')}
            >
              <Workflow className="mr-1.5 size-4" />
              工作流
            </Button>
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-slate-500">测试目标</div>
            <Select value={targetUuid} onValueChange={setTargetUuid}>
              <SelectTrigger className="h-10 w-full bg-white">
                <SelectValue placeholder="选择目标" />
              </SelectTrigger>
              <SelectContent>
                {targetOptions.map((item) => (
                  <SelectItem
                    key={item.uuid}
                    value={item.uuid}
                    description={item.description || item.folder}
                  >
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedTarget && (
              <p className="line-clamp-2 text-xs text-slate-500">
                {selectedTarget.description || selectedTarget.folder || '暂无描述'}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-slate-500">测试场景</div>
            <Textarea
              value={scenario}
              onChange={(event) => setScenario(event.target.value)}
              className="min-h-24 resize-none text-sm"
              placeholder="可留空，系统会按当前目标自动生成客户咨询场景"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                <FileText className="size-3.5" />
                SOP 自动调优
              </div>
              <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
                <Upload className="size-3.5" />
                上传
                <input
                  type="file"
                  accept=".txt,.md,.json,.csv"
                  className="hidden"
                  onChange={(event) =>
                    handleSopFileChange(event.target.files?.[0])
                  }
                />
              </label>
            </div>
            {sopFilename && (
              <div className="truncate text-xs text-cyan-700">
                {sopFilename}
              </div>
            )}
            <Textarea
              value={sopText}
              onChange={(event) => {
                setSopText(event.target.value);
                if (!event.target.value.trim()) setSopFilename('');
              }}
              className="min-h-28 resize-none text-sm"
              placeholder="上传或粘贴 SOP；启动测试后 AI 会按 SOP 模拟客户、评估回复，并自动写回优化配置"
            />
          </div>

          <div className="min-h-0 flex-1 overflow-hidden">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-500">
              <History className="size-3.5" />
              测试记录
            </div>
            <div className="h-full space-y-2 overflow-y-auto pr-1">
              {loadingRuns && (
                <div className="py-6">
                  <LoadingSpinner size="sm" text="加载记录" />
                </div>
              )}
              {!loadingRuns && runs.length === 0 && (
                <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-sm text-slate-500">
                  暂无测试记录
                </div>
              )}
              {!loadingRuns &&
                runs.map((run) => (
                  <button
                    key={run.uuid}
                    type="button"
                    onClick={() => {
                      setSelectedRun(run);
                      setFeedback(run.user_feedback || 'satisfied');
                      setReason(run.feedback_reason || '');
                    }}
                    className={`w-full rounded-lg border p-3 text-left transition hover:border-cyan-300 hover:bg-cyan-50 ${
                      selectedRun?.uuid === run.uuid
                        ? 'border-cyan-400 bg-cyan-50'
                        : 'border-slate-200 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-slate-800">
                        {run.target_name}
                      </span>
                      {run.user_feedback && (
                        <Badge variant="outline">
                          {run.user_feedback === 'satisfied' ? '满意' : '不满意'}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                      {run.scenario}
                    </p>
                    <p className="mt-2 text-[11px] text-slate-400">
                      {formatTime(run.created_at)}
                    </p>
                  </button>
                ))}
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-4 py-3">
            <div className="flex min-w-0 items-center gap-2">
              <MessageSquareText className="size-4 text-slate-500" />
              <span className="truncate text-sm font-semibold text-slate-900">
                {selectedRun ? selectedRun.scenario : '测试对话'}
              </span>
            </div>
            {selectedRun?.evaluation?.score !== undefined && (
              <Badge className="bg-slate-900 text-white">
                {selectedRun.evaluation.score}/{selectedRun.evaluation.max_score}
              </Badge>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50 px-5 py-4">
            {!selectedRun && (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                启动一次自动测试后，这里会展示完整聊天记录
              </div>
            )}
            {selectedRun && (
              <div className="mx-auto flex max-w-3xl flex-col gap-3">
                {selectedRun.messages.map((message, index) => {
                  const isUser = message.role === 'user';
                  return (
                    <div
                      key={`${message.turn}-${message.role}-${index}`}
                      className={`flex ${isUser ? 'justify-start' : 'justify-end'}`}
                    >
                      <div
                        className={`max-w-[82%] rounded-lg border px-3 py-2 text-sm leading-6 shadow-sm ${
                          isUser
                            ? 'border-slate-200 bg-white text-slate-900'
                            : 'border-cyan-200 bg-cyan-700 text-white'
                        }`}
                      >
                        <div
                          className={`mb-1 text-[11px] ${
                            isUser ? 'text-slate-500' : 'text-cyan-100'
                          }`}
                        >
                          {message.sender}
                        </div>
                        {renderMessageContent(message)}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </main>

        <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
          <div>
            <div className="mb-2 text-sm font-semibold text-slate-900">
              本次评估
            </div>
            {!selectedRun && (
              <p className="text-sm text-slate-500">暂无评估结果</p>
            )}
            {selectedRun && (
              <div className="space-y-2">
                {Object.entries(selectedRun.evaluation?.checks || {}).map(
                  ([key, passed]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm"
                    >
                      <span className="text-slate-600">{key}</span>
                      <CheckCircle2
                        className={`size-4 ${
                          passed ? 'text-emerald-600' : 'text-slate-300'
                        }`}
                      />
                    </div>
                  ),
                )}
                {(selectedRun.evaluation?.suggestions || []).map((item) => (
                  <p
                    key={item}
                    className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800"
                  >
                    {item}
                  </p>
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 pt-4">
            <div className="mb-2 text-sm font-semibold text-slate-900">
              人工反馈
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button
                type="button"
                variant={feedback === 'satisfied' ? 'default' : 'outline'}
                className="h-9 rounded-lg"
                disabled={!selectedRun}
                onClick={() => setFeedback('satisfied')}
              >
                <ThumbsUp className="mr-1.5 size-4" />
                满意
              </Button>
              <Button
                type="button"
                variant={feedback === 'unsatisfied' ? 'destructive' : 'outline'}
                className="h-9 rounded-lg"
                disabled={!selectedRun}
                onClick={() => setFeedback('unsatisfied')}
              >
                <ThumbsDown className="mr-1.5 size-4" />
                不满意
              </Button>
            </div>
            {feedback === 'unsatisfied' && (
              <Textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="mt-3 min-h-24 resize-none text-sm"
                placeholder="必须填写不满意原因，AI 会据此追加优化建议"
              />
            )}
            <Button
              type="button"
              className="mt-3 h-9 w-full rounded-lg"
              disabled={
                !selectedRun ||
                submitting ||
                (feedback === 'unsatisfied' && !reason.trim())
              }
              onClick={handleSubmitFeedback}
            >
              {submitting && <Loader2 className="mr-1.5 size-4 animate-spin" />}
              提交反馈
            </Button>
          </div>

          <div className="border-t border-slate-200 pt-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Sparkles className="size-4 text-cyan-600" />
              优化结果
            </div>
            {selectedRun?.optimization_summary ? (
              <div className="rounded-lg bg-cyan-50 p-3 text-sm leading-6 text-cyan-900">
                <p>{selectedRun.optimization_summary}</p>
                {optimizationPatch.operation === 'apply_config_patch' && (
                  <div className="mt-3 border-t border-cyan-100 pt-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge className="bg-cyan-700 text-white">
                        {optimizationPatch.ai_generated ? 'AI 生成补丁' : '规则兜底补丁'}
                      </Badge>
                      {optimizationPatch.model_name && (
                        <span className="text-xs text-cyan-700">
                          {optimizationPatch.model_name}
                        </span>
                      )}
                    </div>
                    <div className="mt-2 text-xs text-cyan-700">
                      保留最近 {optimizationPatch.version_retention || 3} 个版本
                    </div>
                    {appliedPatches.length > 0 && (
                      <div className="mt-3 space-y-2">
                        <div className="text-xs font-medium text-cyan-800">
                          已生效字段
                        </div>
                        {appliedPatches.map((patch) => (
                          <div
                            key={patch.path}
                            className="rounded-md bg-white/75 px-2 py-1.5 font-mono text-[11px] leading-5 text-cyan-950"
                          >
                            {patch.path}
                          </div>
                        ))}
                      </div>
                    )}
                    {optimizationPatch.reverted_at ? (
                      <div className="mt-3 rounded-md bg-slate-100 px-2 py-1.5 text-xs text-slate-600">
                        已撤销：{formatTime(optimizationPatch.reverted_at)}
                      </div>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        className="mt-3 h-8 rounded-md bg-white text-xs"
                        disabled={reverting || appliedPatches.length === 0}
                        onClick={handleRevertOptimization}
                      >
                        {reverting ? (
                          <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                        ) : (
                          <RotateCcw className="mr-1.5 size-3.5" />
                        )}
                        撤销本次修改
                      </Button>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500">
                选择不满意并填写原因后，AI 会自动追加优化建议
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
