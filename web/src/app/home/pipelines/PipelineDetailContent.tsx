import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import PipelineFormComponent from '@/app/home/pipelines/components/pipeline-form/PipelineFormComponent';
import PipelineMonitoringTab from '@/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab';
import PipelineAutoTestTab from '@/app/home/pipelines/components/auto-test/PipelineAutoTestTab';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { BarChart3, Sparkles } from 'lucide-react';

export default function PipelineDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const createType =
    searchParams.get('type') === 'workflow' ? 'workflow' : 'custom';
  const { t } = useTranslation();
  const { refreshPipelines, pipelines, setDetailEntityName } = useSidebarData();

  // Set breadcrumb entity name
  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('pipelines.createPipeline'));
    } else {
      const pipeline = pipelines.find((p) => p.id === id);
      setDetailEntityName(pipeline?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, pipelines, setDetailEntityName, t]);

  const [monitoringOpen, setMonitoringOpen] = useState(false);
  const [autoTestOpen, setAutoTestOpen] = useState(false);
  const [formDirty, setFormDirty] = useState(false);

  function handleFinish() {
    refreshPipelines();
  }

  function handleNewPipelineCreated(newPipelineId: string) {
    refreshPipelines();
    navigate(`/home/pipelines?id=${encodeURIComponent(newPipelineId)}`);
  }

  // ==================== Create Mode ====================
  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex shrink-0 items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h1 className="text-xl font-semibold">
              {t('pipelines.createPipeline')}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {createType === 'workflow'
                ? '创建一个通过工作流库回答客户消息的数字员工'
                : '创建一个可复用的数字员工'}
            </p>
          </div>
          <Button type="submit" form="pipeline-form">
            {t('common.submit')}
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-2xl space-y-6">
            <PipelineFormComponent
              pipelineId={undefined}
              isEditMode={false}
              createMode={createType}
              disableForm={false}
              showButtons={false}
              onFinish={handleFinish}
              onNewPipelineCreated={handleNewPipelineCreated}
              onDeletePipeline={() => {}}
            />
          </div>
        </div>
      </div>
    );
  }

  function handleDeletePipeline() {
    refreshPipelines();
    navigate('/home/pipelines');
  }

  // ==================== Edit Mode ====================
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold">
            {t('pipelines.editPipeline')}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            配置客户消息处理、意图识别、知识检索与回复生成方式
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            className="h-10 rounded-lg px-3 text-cyan-700 hover:bg-cyan-50 hover:text-cyan-900"
            onClick={() => setAutoTestOpen(true)}
          >
            <Sparkles className="mr-1.5 size-4" />
            自动测试
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="h-10 rounded-lg px-3 text-slate-600 hover:bg-slate-100 hover:text-slate-950"
            onClick={() => setMonitoringOpen(true)}
          >
            <BarChart3 className="mr-1.5 size-4" />
            {t('pipelines.monitoring.title')}
          </Button>
          <Button
            type="submit"
            form="pipeline-form"
            disabled={!formDirty}
            className="h-10 rounded-lg px-5 shadow-sm"
          >
            {t('common.save')}
          </Button>
        </div>
      </div>

      <div className="mt-0 flex min-h-0 flex-1 flex-col overflow-hidden">
        <PipelineFormComponent
          pipelineId={id}
          isEditMode={true}
          disableForm={false}
          showButtons={false}
          onFinish={handleFinish}
          onNewPipelineCreated={handleNewPipelineCreated}
          onDeletePipeline={handleDeletePipeline}
          onCancel={() => navigate('/home/pipelines')}
          onDirtyChange={setFormDirty}
        />
      </div>

      <Dialog open={monitoringOpen} onOpenChange={setMonitoringOpen}>
        <DialogContent className="flex h-[78vh] !max-w-[92vw] flex-col rounded-2xl p-6 sm:max-w-[1180px]">
          <PipelineMonitoringTab
            pipelineId={id}
            onNavigateToMonitoring={() => {
              setMonitoringOpen(false);
              navigate('/home/monitoring');
            }}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={autoTestOpen} onOpenChange={setAutoTestOpen}>
        <DialogContent className="flex h-[82vh] !max-w-[94vw] flex-col rounded-2xl p-6 sm:max-w-[1320px]">
          <PipelineAutoTestTab
            initialTargetType="pipeline"
            initialTargetUuid={id}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
