import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import KBForm from '@/app/home/knowledge/components/kb-form/KBForm';
import KBEditDialog from '@/app/home/knowledge/components/kb-form/KBEditDialog';
import KBDoc from '@/app/home/knowledge/components/kb-docs/KBDoc';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { KnowledgeBase } from '@/app/infra/entities/api';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';
import { ChevronRight, Database, MoreHorizontal, Pencil, Trash2 } from 'lucide-react';

export default function KBDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshKnowledgeBases, knowledgeBases, setDetailEntityName } =
    useSidebarData();

  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('knowledge.createKnowledgeBase'));
    } else {
      const kb = knowledgeBases.find((k) => k.id === id);
      setDetailEntityName(kb?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, knowledgeBases, setDetailEntityName, t]);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [kbInfo, setKbInfo] = useState<KnowledgeBase | null>(null);

  const loadKbInfo = useCallback(
    async (kbId: string) => {
      try {
        const resp = await httpClient.getKnowledgeBase(kbId);
        setKbInfo(resp.base);
      } catch (e) {
        console.error('Failed to load KB info:', e);
        toast.error(
          t('knowledge.loadKnowledgeBaseFailed') + (e as CustomApiError).msg,
        );
      }
    },
    [t],
  );

  useEffect(() => {
    if (!isCreateMode) {
      loadKbInfo(id);
    }
  }, [id, isCreateMode, loadKbInfo]);

  function handleKbDeleted() {
    refreshKnowledgeBases();
    navigate('/home/knowledge');
  }

  function handleNewKbCreated(newKbId: string) {
    refreshKnowledgeBases();
    navigate(`/home/knowledge?id=${encodeURIComponent(newKbId)}`);
  }

  function handleKbUpdated() {
    refreshKnowledgeBases();
    loadKbInfo(id);
  }

  async function confirmDelete() {
    try {
      await httpClient.deleteKnowledgeBase(id);
      setShowDeleteConfirm(false);
      handleKbDeleted();
    } catch (e) {
      toast.error(
        t('knowledge.deleteKnowledgeBaseFailed') + (e as CustomApiError).msg,
      );
    }
  }

  const kbDisplayName =
    kbInfo?.name ??
    knowledgeBases.find((k) => k.id === id)?.name ??
    (isCreateMode ? t('knowledge.createKnowledgeBase') : id);

  function renderBreadcrumb(currentLabel: string) {
    return (
      <nav
        aria-label="breadcrumb"
        className="mb-4 flex shrink-0 flex-wrap items-center gap-1 text-sm text-muted-foreground"
      >
        <Button
          type="button"
          variant="link"
          className="h-auto p-0 text-muted-foreground"
          onClick={() => navigate('/home/knowledge')}
        >
          {t('knowledge.title')}
        </Button>
        <ChevronRight className="size-4 shrink-0" />
        <span className="font-medium text-foreground">{currentLabel}</span>
      </nav>
    );
  }

  if (isCreateMode) {
    return (
      <div className="flex h-full min-h-0 flex-col bg-slate-50">
        <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
          {renderBreadcrumb(t('knowledge.createKnowledgeBase'))}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-slate-950">
                {t('knowledge.createKnowledgeBase')}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {t('knowledge.createDialogDescription')}
              </p>
            </div>
            <Button type="submit" form="kb-form">
              {t('common.submit')}
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="mx-auto max-w-3xl pb-8">
            <KBForm
              initKbId={undefined}
              onNewKbCreated={handleNewKbCreated}
              onKbUpdated={handleKbUpdated}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex h-full min-h-0 flex-col bg-slate-50">
        <div className="shrink-0 px-6 pt-4">
          {renderBreadcrumb(kbDisplayName)}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
          <div className="mx-auto max-w-5xl space-y-4">
            <Card className="border-slate-200 bg-white shadow-none">
              <CardContent className="space-y-4 p-5">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
                    <Database className="size-5" />
                  </div>
                  <div className="min-w-0">
                    <h1 className="truncate text-lg font-semibold text-slate-950">
                      {kbDisplayName}
                    </h1>
                    <p className="mt-1 text-sm leading-6 text-slate-500">
                      {kbInfo?.description || t('knowledge.defaultDescription')}
                    </p>
                  </div>
                </div>

                <div className="flex justify-end border-t border-slate-100 pt-3">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="gap-1.5">
                        <MoreHorizontal className="size-4" />
                        {t('knowledge.moreActions')}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setShowEditDialog(true)}>
                        <Pencil className="size-4" />
                        {t('knowledge.editKbInfo')}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => setShowDeleteConfirm(true)}
                      >
                        <Trash2 className="size-4" />
                        {t('common.delete')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardContent>
            </Card>

            <KBDoc
              kbId={id}
              ragEngineName={kbInfo?.knowledge_engine?.name}
              ragEngineCapabilities={kbInfo?.knowledge_engine?.capabilities}
            />
          </div>
        </div>
      </div>

      <KBEditDialog
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
        kbId={id}
        initialName={kbInfo?.name ?? kbDisplayName}
        initialDescription={kbInfo?.description}
        onUpdated={handleKbUpdated}
      />

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription>
              {t('knowledge.deleteKnowledgeBaseConfirmation')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
