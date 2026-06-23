import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Folder,
  FolderPlus,
  Plus,
  Search,
  Trash2,
  Workflow as WorkflowIcon,
} from 'lucide-react';

import PipelineWorkflowEditor from '@/app/home/pipelines/components/workflow-editor/PipelineWorkflowEditor';
import { createBlankWorkflow } from '@/app/home/pipelines/components/workflow-editor/workflowTemplates';
import { PipelineWorkflow } from '@/app/home/pipelines/components/workflow-editor/types';
import type { WorkflowProject } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

type WorkflowItem = {
  id: string;
  folder: string;
  name: string;
  description: string;
  workflow: PipelineWorkflow;
  isBuiltin: boolean;
};

const defaultFolder = '我的项目';

function fromWorkflowProject(project: WorkflowProject): WorkflowItem {
  return {
    id: project.uuid,
    folder: project.folder || defaultFolder,
    name: project.name,
    description: project.description || '',
    workflow: project.workflow as PipelineWorkflow,
    isBuiltin: project.is_builtin || false,
  };
}

export default function WorkflowsPage() {
  const [folders, setFolders] = useState(() => [defaultFolder]);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [activeFolder, setActiveFolder] = useState(defaultFolder);
  const [keyword, setKeyword] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [workflowPendingDeleteId, setWorkflowPendingDeleteId] = useState<
    string | null
  >(null);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    httpClient
      .getWorkflows()
      .then((data) => {
        if (cancelled) return;
        const nextFolders = data.folders.length
          ? data.folders
          : [defaultFolder];
        setFolders(nextFolders);
        setWorkflows((data.workflows || []).map(fromWorkflowProject));
        setActiveFolder((current) =>
          nextFolders.includes(current) ? current : nextFolders[0],
        );
      })
      .catch((error) => {
        toast.error(`工作流加载失败${error?.msg ? `：${error.msg}` : ''}`);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const editingWorkflow = workflows.find((item) => item.id === editingId);
  const workflowPendingDelete = workflows.find(
    (item) => item.id === workflowPendingDeleteId,
  );
  const visibleWorkflows = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return workflows.filter((item) => {
      const inFolder = item.folder === activeFolder;
      const matchesKeyword =
        !normalizedKeyword ||
        `${item.name} ${item.description} ${item.folder}`
          .toLowerCase()
          .includes(normalizedKeyword);
      return inFolder && matchesKeyword;
    });
  }, [activeFolder, keyword, workflows]);

  function updateWorkflow(nextWorkflow: PipelineWorkflow) {
    if (!editingId) return;
    setWorkflows((current) =>
      current.map((item) =>
        item.id === editingId
          ? {
              ...item,
              name: nextWorkflow.name || item.name,
              workflow: nextWorkflow,
            }
          : item,
      ),
    );
  }

  async function createNewWorkflow() {
    const workflow = createBlankWorkflow();
    const payload = {
      folder: activeFolder,
      name: '新建工作流',
      description: '从空白画布开始搭建新的自动化流程。',
      workflow: {
        ...workflow,
        name: '新建工作流',
      },
    };
    let resp: { uuid: string };
    try {
      resp = await httpClient.createWorkflow(payload);
    } catch (error: any) {
      toast.error(`工作流创建失败${error?.msg ? `：${error.msg}` : ''}`);
      return;
    }
    setWorkflows((current) => [
      {
        id: resp.uuid,
        ...payload,
        isBuiltin: false,
      },
      ...current,
    ]);
    setEditingId(resp.uuid);
  }

  async function createFolder() {
    const folderName = newFolderName.trim();
    if (!folderName || folders.includes(folderName)) {
      setCreatingFolder(false);
      setNewFolderName('');
      return;
    }

    try {
      await httpClient.createWorkflowFolder(folderName);
    } catch (error: any) {
      toast.error(`目录创建失败${error?.msg ? `：${error.msg}` : ''}`);
      return;
    }
    setFolders((current) => [...current, folderName]);
    setActiveFolder(folderName);
    setCreatingFolder(false);
    setNewFolderName('');
  }

  async function deleteWorkflow() {
    if (!workflowPendingDeleteId) return;
    try {
      await httpClient.deleteWorkflow(workflowPendingDeleteId);
    } catch (error: any) {
      toast.error(`工作流删除失败${error?.msg ? `：${error.msg}` : ''}`);
      return;
    }
    setWorkflows((current) =>
      current.filter((item) => item.id !== workflowPendingDeleteId),
    );
    if (editingId === workflowPendingDeleteId) {
      setEditingId(null);
    }
    setWorkflowPendingDeleteId(null);
  }

  async function saveEditingWorkflow() {
    if (!editingWorkflow) return;
    setSaving(true);
    try {
      await httpClient.updateWorkflow(editingWorkflow.id, {
        folder: editingWorkflow.folder,
        name: editingWorkflow.name,
        description: editingWorkflow.description,
        workflow: editingWorkflow.workflow,
      });
      setEditingId(null);
      toast.success('工作流已保存');
    } catch (error: any) {
      toast.error(`工作流保存失败${error?.msg ? `：${error.msg}` : ''}`);
    } finally {
      setSaving(false);
    }
  }

  if (editingWorkflow) {
    return (
      <div className="flex h-full min-h-0 flex-col bg-slate-50 text-slate-900">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-9"
              onClick={() => setEditingId(null)}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold text-slate-950">
                {editingWorkflow.name}
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                {editingWorkflow.workflow.nodes.length} 个节点，
                {editingWorkflow.workflow.edges.length} 条连线
              </p>
            </div>
          </div>
          <Button type="button" onClick={saveEditingWorkflow} disabled={saving}>
            {saving ? '保存中' : '保存并返回'}
          </Button>
        </header>
        <div className="min-h-0 flex-1">
          <PipelineWorkflowEditor
            value={editingWorkflow.workflow}
            onChange={updateWorkflow}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-[#f5f7fb] text-slate-950">
      <header className="shrink-0 px-5 pb-5 pt-6 lg:px-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">工作流</h1>
            <p className="mt-2 text-base text-slate-500">
              您可以工作流模块设计和配置您的工作流，以便实现各种复杂业务流程。
            </p>
          </div>
          <Button
            type="button"
            className="mt-1 h-11 rounded-md bg-indigo-600 px-5 text-white hover:bg-indigo-700"
            onClick={createNewWorkflow}
            disabled={loading}
          >
            <Plus className="size-4" />
            新建工作流
          </Button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="min-h-0 max-h-64 border-b border-slate-200/80 px-5 pb-4 lg:max-h-none lg:border-b-0 lg:border-r lg:px-7 lg:pb-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">目录</h2>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="size-10 rounded-lg border-slate-200 bg-white"
                title="创建新目录"
                onClick={() => setCreatingFolder(true)}
              >
                <FolderPlus className="size-5" />
              </Button>
            </div>
          </div>
          <div className="h-[calc(100%-56px)] overflow-y-auto pr-2">
            {creatingFolder && (
              <div className="mb-3 rounded-lg border border-slate-200 bg-white p-3">
                <Input
                  value={newFolderName}
                  onChange={(event) => setNewFolderName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      createFolder();
                    }
                    if (event.key === 'Escape') {
                      setCreatingFolder(false);
                      setNewFolderName('');
                    }
                  }}
                  placeholder="新目录名称"
                  className="h-9"
                  autoFocus
                />
                <div className="mt-2 flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setCreatingFolder(false);
                      setNewFolderName('');
                    }}
                  >
                    取消
                  </Button>
                  <Button type="button" size="sm" onClick={createFolder}>
                    创建
                  </Button>
                </div>
              </div>
            )}
            <div className="space-y-2">
              {folders.map((folder) => (
                <button
                  key={folder}
                  type="button"
                  className={cn(
                    'flex h-11 w-full items-center gap-3 rounded-md px-3 text-left text-base font-medium text-slate-500 transition',
                    activeFolder === folder
                      ? 'bg-indigo-50 text-indigo-600'
                      : 'hover:bg-white hover:text-slate-900',
                  )}
                  onClick={() => setActiveFolder(folder)}
                >
                  <Folder className="size-5 shrink-0" />
                  <span className="truncate">{folder}</span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="min-h-0 overflow-y-auto px-5 pb-8 lg:px-9">
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <div className="relative w-full max-w-[360px]">
              <Search className="absolute right-4 top-1/2 size-5 -translate-y-1/2 text-slate-500" />
              <Input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                className="h-14 rounded-lg border-slate-200 bg-white px-7 pr-12 text-base shadow-none"
                placeholder="搜索流程和组件"
              />
            </div>
          </div>

          {loading ? (
            <div className="mt-12 rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
              正在加载工作流...
            </div>
          ) : (
            <div className="grid gap-5 xl:grid-cols-2 2xl:grid-cols-3">
              {visibleWorkflows.map((item) => {
                return (
                  <article
                    key={item.id}
                    role="button"
                    tabIndex={0}
                    className="group/card relative min-h-[168px] cursor-pointer rounded-2xl bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                    onClick={() => setEditingId(item.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setEditingId(item.id);
                      }
                    }}
                  >
                    {!item.isBuiltin && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="absolute right-4 top-4 size-9 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover/card:opacity-100"
                        title="删除工作流"
                        onClick={(event) => {
                          event.stopPropagation();
                          setWorkflowPendingDeleteId(item.id);
                        }}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    )}

                    <div className="mb-5 flex items-start gap-4 pr-10">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500 text-white shadow-sm">
                        <WorkflowIcon className="size-5" />
                      </span>
                      <div className="min-w-0">
                        <h2 className="truncate text-xl font-semibold text-slate-950">
                          {item.name}
                        </h2>
                      </div>
                    </div>

                    <p className="line-clamp-2 min-h-[52px] text-base leading-7 text-slate-500">
                      {item.description}
                    </p>
                  </article>
                );
              })}
            </div>
          )}

          <AlertDialog
            open={!!workflowPendingDelete}
            onOpenChange={(open) => {
              if (!open) {
                setWorkflowPendingDeleteId(null);
              }
            }}
          >
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确认删除工作流</AlertDialogTitle>
                <AlertDialogDescription>
                  删除后无法恢复，确定要删除
                  {workflowPendingDelete
                    ? `「${workflowPendingDelete.name}」`
                    : ''}
                  吗？
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction
                  className="bg-red-600 text-white hover:bg-red-700"
                  onClick={deleteWorkflow}
                >
                  删除
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {!loading && visibleWorkflows.length === 0 && (
            <div className="mt-12 flex min-h-[280px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white">
              <div className="text-center">
                <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <WorkflowIcon className="size-6" />
                </div>
                <h2 className="mt-4 text-lg font-semibold">暂无工作流</h2>
                <p className="mt-2 text-sm text-slate-500">
                  换一个目录，或新建一个工作流。
                </p>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
