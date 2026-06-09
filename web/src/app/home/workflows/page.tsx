import { useMemo, useState } from 'react';
import {
  ArrowLeft,
  Copy,
  Download,
  Edit3,
  Folder,
  FolderPlus,
  Plus,
  Search,
  Trash2,
  Workflow as WorkflowIcon,
} from 'lucide-react';

import PipelineWorkflowEditor from '@/app/home/pipelines/components/workflow-editor/PipelineWorkflowEditor';
import {
  createBlankWorkflow,
  createCourseSalesWorkflowTemplate,
  createTaskAssistantWorkflowTemplate,
} from '@/app/home/pipelines/components/workflow-editor/workflowTemplates';
import { PipelineWorkflow } from '@/app/home/pipelines/components/workflow-editor/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

type WorkflowItem = {
  id: string;
  folder: string;
  name: string;
  description: string;
  workflow: PipelineWorkflow;
};

const initialFolders = ['我的项目'];

function createInitialWorkflowItems(): WorkflowItem[] {
  const courseSalesWorkflow = createCourseSalesWorkflowTemplate();
  const taskAssistantWorkflow = createTaskAssistantWorkflowTemplate();

  return [
    {
      id: 'course-sales-template',
      folder: '我的项目',
      name: '课程销售模板',
      description: '承接图书资源咨询、自然拼读课程答疑、报名转化、雷达跟进和人工接管。',
      workflow: courseSalesWorkflow,
    },
    {
      id: 'task-assistant-template',
      folder: '我的项目',
      name: '任务助手模板配置版',
      description: '引导用户完成蚂蚁阿福实名认证，保留步骤图片、截图识别和语音回复节点。',
      workflow: taskAssistantWorkflow,
    },
  ];
}

function workflowCardMeta(item: WorkflowItem) {
  return {
    nodeCount: item.workflow.nodes.length,
    updatedAt: item.workflow.metadata?.source_mode === 'template' ? '模板迁移' : '画布模板',
  };
}

export default function WorkflowsPage() {
  const [folders, setFolders] = useState(() => [...initialFolders]);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>(() => createInitialWorkflowItems());
  const [activeFolder, setActiveFolder] = useState('我的项目');
  const [keyword, setKeyword] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');

  const editingWorkflow = workflows.find((item) => item.id === editingId);
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

  function toggleSelected(id: string) {
    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((selectedId) => selectedId !== id)
        : [...current, id],
    );
  }

  function toggleSelectAll() {
    if (selectedIds.length === visibleWorkflows.length) {
      setSelectedIds([]);
      return;
    }
    setSelectedIds(visibleWorkflows.map((item) => item.id));
  }

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

  function createNewWorkflow() {
    const workflow = createBlankWorkflow();
    const id = `workflow-${Date.now()}`;
    setWorkflows((current) => [
      {
        id,
        folder: activeFolder,
        name: '新建工作流',
        description: '从空白画布开始搭建新的自动化流程。',
        workflow: {
          ...workflow,
          name: '新建工作流',
        },
      },
      ...current,
    ]);
    setEditingId(id);
  }

  function createFolder() {
    const folderName = newFolderName.trim();
    if (!folderName || folders.includes(folderName)) {
      setCreatingFolder(false);
      setNewFolderName('');
      return;
    }

    setFolders((current) => [...current, folderName]);
    setActiveFolder(folderName);
    setCreatingFolder(false);
    setNewFolderName('');
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
                {editingWorkflow.workflow.nodes.length} 个节点，{editingWorkflow.workflow.edges.length} 条连线
              </p>
            </div>
          </div>
          <Button type="button" onClick={() => setEditingId(null)}>
            保存并返回
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
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
            <div className="relative w-full max-w-[360px]">
              <Search className="absolute right-4 top-1/2 size-5 -translate-y-1/2 text-slate-500" />
              <Input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                className="h-14 rounded-lg border-slate-200 bg-white px-7 pr-12 text-base shadow-none"
                placeholder="搜索流程和组件"
              />
            </div>
            <div className="flex items-center gap-4 text-slate-700">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-9"
              >
                <Download className="size-5" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-9"
              >
                <Copy className="size-5" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-9"
              >
                <Trash2 className="size-5" />
              </Button>
            </div>
          </div>

          <label className="mb-7 flex w-fit items-center gap-3 text-base font-semibold">
            <input
              type="checkbox"
              className="size-5 rounded border-slate-300"
              checked={
                visibleWorkflows.length > 0 &&
                selectedIds.length === visibleWorkflows.length
              }
              onChange={toggleSelectAll}
            />
            全选
          </label>

          <div className="grid gap-5 xl:grid-cols-2 2xl:grid-cols-3">
            {visibleWorkflows.map((item) => {
              const meta = workflowCardMeta(item);
              const selected = selectedIds.includes(item.id);
              return (
                <article
                  key={item.id}
                  className="min-h-[200px] rounded-2xl bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:shadow-md"
                >
                  <div className="mb-5 flex items-start justify-between gap-4">
                    <button
                      type="button"
                      className="flex min-w-0 items-center gap-4 text-left"
                      onClick={() => setEditingId(item.id)}
                    >
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500 text-white shadow-sm">
                        <WorkflowIcon className="size-5" />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-xl font-semibold text-slate-950">
                          {item.name}
                        </span>
                        <span className="mt-1 block text-sm text-slate-400">
                          {meta.nodeCount} 个节点 · {meta.updatedAt}
                        </span>
                      </span>
                    </button>
                    <input
                      type="checkbox"
                      className="mt-1 size-6 rounded border-slate-300"
                      checked={selected}
                      onChange={() => toggleSelected(item.id)}
                    />
                  </div>

                  <p className="line-clamp-2 min-h-[52px] text-base leading-7 text-slate-500">
                    {item.description}
                  </p>

                  <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4">
                    <span className="text-sm text-slate-400">
                      {item.folder}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-8 gap-2 px-2 text-base font-semibold text-slate-800 hover:bg-slate-50"
                      onClick={() => setEditingId(item.id)}
                    >
                      <Edit3 className="size-4" />
                      编辑
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>

          {visibleWorkflows.length === 0 && (
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
