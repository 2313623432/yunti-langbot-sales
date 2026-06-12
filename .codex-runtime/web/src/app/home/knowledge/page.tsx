import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import KBMigrationDialog from '@/app/home/knowledge/components/kb-migration-dialog/KBMigrationDialog';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import KBDetailContent from './KBDetailContent';
import KBCard from '@/app/home/knowledge/components/kb-card/KBCard';
import KBCreateDialog from '@/app/home/knowledge/components/kb-form/KBCreateDialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import { Database, Plus, Search } from 'lucide-react';
import { KnowledgeBase } from '@/app/infra/entities/api';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';

const PAGE_SIZE = 9;

export default function KnowledgePage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');
  const navigate = useNavigate();
  const { refreshKnowledgeBases, setDetailEntityName } = useSidebarData();

  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [kbList, setKbList] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  const [migrationDialogOpen, setMigrationDialogOpen] = useState(false);
  const [migrationInternalCount, setMigrationInternalCount] = useState(0);
  const [migrationExternalCount, setMigrationExternalCount] = useState(0);

  const loadKnowledgeBases = async () => {
    setLoading(true);
    try {
      const resp = await httpClient.getKnowledgeBases();
      setKbList(resp.bases);
    } catch (error) {
      console.error('Failed to load knowledge bases:', error);
      toast.error(
        t('knowledge.getKnowledgeBaseListError') +
          (error as CustomApiError).msg,
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkMigrationStatus();
  }, []);

  useEffect(() => {
    if (!detailId) {
      setDetailEntityName(null);
      loadKnowledgeBases();
    }
  }, [detailId, setDetailEntityName]);

  async function checkMigrationStatus() {
    try {
      const resp = await httpClient.getRagMigrationStatus();
      if (resp.needed) {
        setMigrationInternalCount(resp.internal_kb_count);
        setMigrationExternalCount(resp.external_kb_count);
        setMigrationDialogOpen(true);
      }
    } catch {
      // Silently ignore - migration check is non-critical
    }
  }

  function handleMigrationComplete() {
    refreshKnowledgeBases();
    if (!detailId) {
      loadKnowledgeBases();
    }
  }

  function handleKbCreated(kbId: string) {
    refreshKnowledgeBases();
    loadKnowledgeBases();
    navigate(`/home/knowledge?id=${encodeURIComponent(kbId)}`);
  }

  const filteredBases = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    if (!normalizedKeyword) return kbList;

    return kbList.filter((kb) => {
      return [kb.name, kb.description]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(normalizedKeyword));
    });
  }, [keyword, kbList]);

  const pageCount = Math.max(1, Math.ceil(filteredBases.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const visibleBases = filteredBases.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );

  useEffect(() => {
    setPage(1);
  }, [keyword, kbList.length]);

  if (detailId) {
    return (
      <>
        <KBMigrationDialog
          open={migrationDialogOpen}
          onOpenChange={setMigrationDialogOpen}
          internalKbCount={migrationInternalCount}
          externalKbCount={migrationExternalCount}
          onMigrationComplete={handleMigrationComplete}
        />
        <KBDetailContent id={detailId} />
      </>
    );
  }

  return (
    <>
      <KBMigrationDialog
        open={migrationDialogOpen}
        onOpenChange={setMigrationDialogOpen}
        internalKbCount={migrationInternalCount}
        externalKbCount={migrationExternalCount}
        onMigrationComplete={handleMigrationComplete}
      />

      <div className="flex h-full min-h-0 flex-col bg-slate-50 text-slate-900">
        <div className="shrink-0 px-6 pb-5 pt-4">
          <div className="mb-4">
            <h1 className="text-2xl font-semibold text-slate-950">
              {t('knowledge.title')}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              {t('knowledge.description')}
            </p>
          </div>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative w-full sm:max-w-md">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                className="h-11 border-slate-200 bg-white pl-9 text-sm"
                placeholder={t('knowledge.searchPlaceholder')}
              />
            </div>
            <Button className="h-11 px-6" onClick={() => setShowCreateDialog(true)}>
              <Plus className="size-4" />
              {t('knowledge.createKnowledgeBase')}
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-5">
          {loading ? (
            <div className="flex h-full min-h-[360px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white text-sm text-slate-500">
              {t('common.loading')}
            </div>
          ) : visibleBases.length > 0 ? (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {visibleBases.map((kb) => {
                const supportsDocuments =
                  kb.knowledge_engine?.capabilities?.includes('doc_ingestion') ??
                  true;

                return (
                  <KBCard
                    key={kb.uuid}
                    id={kb.uuid || ''}
                    name={kb.name}
                    description={kb.description}
                    supportsDocuments={supportsDocuments}
                    fileCount={kb.file_count}
                    updatedAt={kb.updated_at}
                    onClick={() =>
                      navigate(
                        `/home/knowledge?id=${encodeURIComponent(kb.uuid || '')}`,
                      )
                    }
                    onUpdated={loadKnowledgeBases}
                    onDeleted={() => {
                      refreshKnowledgeBases();
                      loadKnowledgeBases();
                    }}
                  />
                );
              })}
            </div>
          ) : (
            <div className="flex h-full min-h-[360px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white">
              <div className="flex max-w-sm flex-col items-center gap-3 text-center">
                <div className="flex size-12 items-center justify-center rounded-full bg-violet-50 text-violet-600">
                  <Database className="size-6" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-slate-900">
                    {t('knowledge.emptyListTitle')}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {t('knowledge.emptyListDescription')}
                  </p>
                </div>
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="size-4" />
                  {t('knowledge.createKnowledgeBase')}
                </Button>
              </div>
            </div>
          )}
        </div>

        {filteredBases.length > PAGE_SIZE && (
          <div className="shrink-0 border-t border-slate-100 bg-slate-50 px-6 py-4">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    onClick={(event) => {
                      event.preventDefault();
                      setPage((current) => Math.max(1, current - 1));
                    }}
                    className={
                      safePage === 1 ? 'pointer-events-none opacity-50' : ''
                    }
                  />
                </PaginationItem>
                {Array.from({ length: pageCount }, (_, index) => index + 1).map(
                  (pageNumber) => (
                    <PaginationItem key={pageNumber}>
                      <PaginationLink
                        href="#"
                        isActive={pageNumber === safePage}
                        onClick={(event) => {
                          event.preventDefault();
                          setPage(pageNumber);
                        }}
                      >
                        {pageNumber}
                      </PaginationLink>
                    </PaginationItem>
                  ),
                )}
                <PaginationItem>
                  <PaginationNext
                    href="#"
                    onClick={(event) => {
                      event.preventDefault();
                      setPage((current) => Math.min(pageCount, current + 1));
                    }}
                    className={
                      safePage === pageCount
                        ? 'pointer-events-none opacity-50'
                        : ''
                    }
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}
      </div>

      <KBCreateDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onCreated={handleKbCreated}
      />
    </>
  );
}
