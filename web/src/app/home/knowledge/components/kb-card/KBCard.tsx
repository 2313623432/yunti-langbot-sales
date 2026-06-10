import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Database, FileText, MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatKbUpdatedAt } from '@/app/home/knowledge/utils/formatKbUpdatedAt';
import KBEditDialog from '@/app/home/knowledge/components/kb-form/KBEditDialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';

export interface KBCardProps {
  id: string;
  name: string;
  description?: string;
  supportsDocuments?: boolean;
  fileCount?: number;
  updatedAt?: string;
  onClick: () => void;
  onUpdated: () => void;
  onDeleted: () => void;
}

export default function KBCard({
  id,
  name,
  description,
  supportsDocuments,
  fileCount,
  updatedAt,
  onClick,
  onUpdated,
  onDeleted,
}: KBCardProps) {
  const { t } = useTranslation();
  const updatedLabel = formatKbUpdatedAt(updatedAt, t);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  async function confirmDelete() {
    try {
      await httpClient.deleteKnowledgeBase(id);
      setShowDeleteConfirm(false);
      toast.success(t('knowledge.deleteKnowledgeBaseSuccess'));
      onDeleted();
    } catch (error) {
      toast.error(
        t('knowledge.deleteKnowledgeBaseFailed') + (error as CustomApiError).msg,
      );
    }
  }

  return (
    <>
      <Card
        className={cn(
          'min-h-[220px] gap-0 overflow-hidden rounded-lg border-slate-100 bg-white py-0 shadow-none transition',
          'hover:border-blue-200 hover:shadow-sm',
        )}
      >
        <button
          type="button"
          className="flex flex-1 flex-col text-left"
          onClick={onClick}
        >
          <CardContent className="flex flex-1 flex-col px-5 pb-0 pt-6">
            <div className="flex items-start gap-3">
              <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
                <Database className="size-6" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-base font-semibold text-slate-900">
                  {name}
                </h2>
              </div>
            </div>

            <p className="mt-4 line-clamp-2 min-h-[48px] text-sm leading-6 text-slate-500">
              {description || t('knowledge.defaultDescription')}
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
              {supportsDocuments && (
                <span className="inline-flex items-center gap-1">
                  <FileText className="size-3.5" />
                  {t('knowledge.fileCountLabel', { count: fileCount ?? 0 })}
                </span>
              )}
              {updatedLabel && <span>{updatedLabel}</span>}
            </div>
          </CardContent>
        </button>

        <CardFooter className="mt-auto flex items-center justify-between border-t border-slate-100 px-5 py-3">
          <span className="text-xs text-slate-400">{t('knowledge.cardHint')}</span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-slate-500"
                onClick={(event) => event.stopPropagation()}
              >
                <MoreHorizontal className="size-4" />
                <span className="sr-only">{t('knowledge.moreActions')}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={(event) => event.stopPropagation()}>
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
        </CardFooter>
      </Card>

      <KBEditDialog
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
        kbId={id}
        initialName={name}
        initialDescription={description}
        onUpdated={onUpdated}
      />

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent onClick={(event) => event.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription>
              {t('knowledge.deleteKnowledgeBaseConfirmation')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
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
