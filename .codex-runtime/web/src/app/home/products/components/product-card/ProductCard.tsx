import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  MoreHorizontal,
  Package,
  Pencil,
  Tag,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';

import { formatProductUpdatedAt } from '@/app/home/products/utils/formatProductUpdatedAt';
import {
  isSampleProduct,
} from '@/app/home/products/utils/productUtils';
import { SalesProduct } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { CustomApiError } from '@/app/infra/entities/common';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

export interface ProductCardProps {
  product: SalesProduct;
  onClick: () => void;
  onDeleted: () => void;
}

export default function ProductCard({
  product,
  onClick,
  onDeleted,
}: ProductCardProps) {
  const { t } = useTranslation();
  const updatedLabel = formatProductUpdatedAt(product.updated_at, t);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  async function confirmDelete() {
    if (!product.uuid) return;
    try {
      await httpClient.deleteSalesProduct(product.uuid);
      setShowDeleteConfirm(false);
      toast.success(t('productLibrary.deleteSuccess'));
      onDeleted();
    } catch (error) {
      toast.error(
        t('productLibrary.deleteFailed') + (error as CustomApiError).msg,
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
              <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-sky-700">
                <Package className="size-6" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate text-base font-semibold text-slate-900">
                    {product.name}
                  </h2>
                  <Badge
                    variant="outline"
                    className={
                      product.enabled
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-slate-200 bg-slate-50 text-slate-500'
                    }
                  >
                    {product.enabled
                      ? t('productLibrary.statusEnabled')
                      : t('productLibrary.statusDisabled')}
                  </Badge>
                  {isSampleProduct(product) && (
                    <Badge variant="outline" className="text-slate-500">
                      {t('productLibrary.sampleBadge')}
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            <p className="mt-4 line-clamp-2 min-h-[48px] text-sm leading-6 text-slate-500">
              {product.description || t('productLibrary.noDescription')}
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
              {product.product_line && (
                <Badge variant="outline" className="border-indigo-200 bg-indigo-50 text-indigo-700">
                  {product.product_line}
                </Badge>
              )}
              {product.category && (
                <span className="inline-flex items-center gap-1">
                  <Tag className="size-3.5" />
                  {product.category}
                </span>
              )}
              {product.price && <span>{product.price}</span>}
              {updatedLabel && <span>{updatedLabel}</span>}
            </div>

            {(product.selling_points || []).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(product.selling_points || []).slice(0, 3).map((point) => (
                  <Badge
                    key={point}
                    variant="secondary"
                    className="bg-sky-50 text-sky-700"
                  >
                    {point}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </button>

        <CardFooter className="mt-auto flex items-center justify-between border-t border-slate-100 px-5 py-3">
          <span className="text-xs text-slate-400">
            {t('productLibrary.cardHint')}
          </span>
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
                <span className="sr-only">{t('productLibrary.moreActions')}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              onClick={(event) => event.stopPropagation()}
            >
              <DropdownMenuItem onClick={onClick}>
                <Pencil className="size-4" />
                {t('common.edit')}
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

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent onClick={(event) => event.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription>
              {t('productLibrary.deleteConfirmation')}
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
