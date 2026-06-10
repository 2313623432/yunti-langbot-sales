import { ColumnDef } from '@tanstack/react-table';
import { FileText, MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { TFunction } from 'i18next';

export type DocumentFile = {
  uuid: string;
  name: string;
  status: string;
  createdAt?: string;
  chunkCount?: number;
};

function formatFileDate(value?: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString();
}

function StatusBadge({ status, t }: { status: string; t: TFunction }) {
  switch (status) {
    case 'processing':
    case 'pending':
      return (
        <Badge variant="secondary">
          {status === 'pending'
            ? t('knowledge.documentsTab.statusPending')
            : t('knowledge.documentsTab.processing')}
        </Badge>
      );
    case 'completed':
      return (
        <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
          {t('knowledge.documentsTab.statusCompleted')}
        </Badge>
      );
    case 'failed':
      return (
        <Badge variant="destructive">
          {t('knowledge.documentsTab.statusFailed')}
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export const columns = (
  onDelete: (id: string) => void,
  t: TFunction,
): ColumnDef<DocumentFile>[] => {
  return [
    {
      accessorKey: 'name',
      header: t('knowledge.documentsTab.name'),
      cell: ({ row }) => {
        const document = row.original;
        return (
          <div className="flex min-w-0 items-center gap-2">
            <FileText className="size-4 shrink-0 text-slate-400" />
            <span className="truncate font-medium text-slate-900">
              {document.name}
            </span>
          </div>
        );
      },
    },
    {
      accessorKey: 'status',
      header: t('knowledge.documentsTab.learningProgress'),
      cell: ({ row }) => (
        <StatusBadge status={row.original.status} t={t} />
      ),
    },
    {
      accessorKey: 'createdAt',
      header: t('knowledge.documentsTab.uploadedAt'),
      cell: ({ row }) => (
        <span className="text-sm text-slate-500">
          {formatFileDate(row.original.createdAt)}
        </span>
      ),
    },
    {
      id: 'actions',
      cell: ({ row }) => {
        const document = row.original;

        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <span className="sr-only">
                  {t('knowledge.documentsTab.actions')}
                </span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="bg-white dark:bg-[#2a2a2e]"
            >
              <DropdownMenuLabel>
                {t('knowledge.documentsTab.actions')}
              </DropdownMenuLabel>

              <DropdownMenuItem onClick={() => onDelete(document.uuid)}>
                {t('knowledge.documentsTab.delete')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];
};
