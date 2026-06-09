import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PipelineDetailContent from './PipelineDetailContent';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import { Bot, Copy, MoreHorizontal, Plus, Search, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

const PAGE_SIZE = 8;

const avatarPalettes = [
  'bg-blue-100 text-blue-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-pink-100 text-pink-700',
];

export default function PipelineConfigPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');
  const navigate = useNavigate();
  const { pipelines, refreshPipelines, setDetailEntityName } =
    useSidebarData();
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [pipelineToDelete, setPipelineToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);

  useEffect(() => {
    if (!detailId) {
      setDetailEntityName(null);
    }
  }, [detailId, setDetailEntityName]);

  const filteredPipelines = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    if (!normalizedKeyword) return pipelines;

    return pipelines.filter((pipeline) => {
      return [pipeline.name, pipeline.description]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(normalizedKeyword));
    });
  }, [keyword, pipelines]);

  const pageCount = Math.max(
    1,
    Math.ceil(filteredPipelines.length / PAGE_SIZE),
  );
  const safePage = Math.min(page, pageCount);
  const visiblePipelines = filteredPipelines.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );

  useEffect(() => {
    setPage(1);
  }, [keyword, pipelines.length]);

  function goToCreate() {
    navigate('/home/pipelines?id=new');
  }

  function copyPipeline(pipelineId: string) {
    httpClient
      .copyPipeline(pipelineId)
      .then(() => {
        refreshPipelines();
        toast.success(t('common.copySuccess'));
      })
      .catch((err) => {
        toast.error(t('common.copyFailed') + (err.msg ? `：${err.msg}` : ''));
      });
  }

  function confirmDeletePipeline() {
    if (!pipelineToDelete) return;

    httpClient
      .deletePipeline(pipelineToDelete.id)
      .then(() => {
        setPipelineToDelete(null);
        refreshPipelines();
        toast.success(t('pipelines.deleteSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.deleteError') + err.msg);
      });
  }

  if (detailId) {
    return <PipelineDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-50 text-slate-900">
      <div className="shrink-0 px-6 pb-5 pt-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <label
              htmlFor="pipeline-search"
              className="shrink-0 text-sm font-medium text-slate-700"
            >
              角色名称
            </label>
            <div className="relative sm:w-[360px]">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                id="pipeline-search"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                className="h-11 border-slate-200 bg-white pl-9 text-sm"
                placeholder="输入角色进行搜索"
              />
            </div>
          </div>
          <Button className="h-11 px-6" onClick={goToCreate}>
            <Plus className="size-4" />
            {t('pipelines.createPipeline')}
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-5">
        {visiblePipelines.length > 0 ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {visiblePipelines.map((pipeline, index) => (
              <Card
                key={pipeline.id}
                className="min-h-[300px] gap-0 overflow-hidden rounded-lg border-slate-100 bg-white py-0 shadow-none transition hover:border-blue-200 hover:shadow-sm"
              >
                <button
                  type="button"
                  className="flex flex-1 flex-col text-left"
                  onClick={() =>
                    navigate(
                      `/home/pipelines?id=${encodeURIComponent(pipeline.id)}`,
                    )
                  }
                >
                  <CardContent className="flex flex-1 flex-col items-center px-5 pb-0 pt-10">
                    <div
                      className={cn(
                        'flex size-24 items-center justify-center rounded-full text-4xl font-semibold',
                        avatarPalettes[index % avatarPalettes.length],
                      )}
                    >
                      {pipeline.iconURL ? (
                        <img
                          src={pipeline.iconURL}
                          alt={`${pipeline.name} 头像`}
                          className="size-full rounded-full object-cover"
                        />
                      ) : pipeline.emoji || pipeline.name.slice(0, 1) || (
                        <Bot className="size-10" />
                      )}
                    </div>
                    <h2 className="mt-4 max-w-full truncate text-center text-base font-semibold text-slate-900">
                      {pipeline.name}
                    </h2>
                    <p className="mt-2 line-clamp-3 min-h-[72px] w-full text-sm leading-6 text-slate-500">
                      {pipeline.description ||
                        `Hi，我是${pipeline.name}，正在等待配置更多能力。`}
                    </p>
                  </CardContent>

                </button>
                <CardFooter className="mt-auto flex items-center justify-end border-t border-slate-100 px-5 py-4 text-slate-400">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-8 text-slate-400 hover:text-slate-700"
                        aria-label={`${pipeline.name} 更多操作`}
                      >
                        <MoreHorizontal className="size-5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuGroup>
                        <DropdownMenuItem
                          onClick={() => copyPipeline(pipeline.id)}
                        >
                          <Copy />
                          {t('common.copy')}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          variant="destructive"
                          disabled={pipeline.isDefault}
                          onClick={() =>
                            setPipelineToDelete({
                              id: pipeline.id,
                              name: pipeline.name,
                            })
                          }
                        >
                          <Trash2 />
                          {t('common.delete')}
                        </DropdownMenuItem>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </CardFooter>
              </Card>
            ))}
          </div>
        ) : (
          <div className="flex h-full min-h-[360px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white">
            <div className="flex max-w-sm flex-col items-center gap-3 text-center">
              <div className="flex size-12 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                <Bot className="size-6" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  暂无数字员工
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  创建一个数字员工后，可在这里统一查看和进入配置。
                </p>
              </div>
              <Button onClick={goToCreate}>
                <Plus className="size-4" />
                {t('pipelines.createPipeline')}
              </Button>
            </div>
          </div>
        )}
      </div>

      {filteredPipelines.length > PAGE_SIZE && (
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

      <Dialog
        open={pipelineToDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPipelineToDelete(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <div className="py-4 text-sm leading-6 text-slate-600">
            {t('pipelines.deleteConfirmation')}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPipelineToDelete(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDeletePipeline}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
