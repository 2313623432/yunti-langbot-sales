import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ChevronRight,
  MoreHorizontal,
  Package,
  Pencil,
  Save,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';

import ProductForm from '@/app/home/products/components/product-form/ProductForm';
import {
  type ProductDraft,
  draftToPayload,
  emptyProductDraft,
  errorMessage,
  isSampleProduct,
  productToDraft,
} from '@/app/home/products/utils/productUtils';
import { SalesProduct } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { CustomApiError } from '@/app/infra/entities/common';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
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

export default function ProductDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { setDetailEntityName } = useSidebarData();

  const [productInfo, setProductInfo] = useState<SalesProduct | null>(null);
  const [draft, setDraft] = useState<ProductDraft>(emptyProductDraft);
  const [loading, setLoading] = useState(!isCreateMode);
  const [saving, setSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const loadProduct = useCallback(
    async (productId: string) => {
      setLoading(true);
      try {
        const resp = await httpClient.getSalesProduct(productId);
        setProductInfo(resp.product);
        setDraft(productToDraft(resp.product));
        setDetailEntityName(resp.product.name);
      } catch (error) {
        console.error('Failed to load product:', error);
        toast.error(
          t('productLibrary.loadProductFailed') +
            (error as CustomApiError).msg,
        );
      } finally {
        setLoading(false);
      }
    },
    [setDetailEntityName, t],
  );

  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('productLibrary.createProduct'));
      setDraft(emptyProductDraft);
      return () => setDetailEntityName(null);
    }

    void loadProduct(id);
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, loadProduct, setDetailEntityName, t]);

  const displayName =
    productInfo?.name ??
    (isCreateMode ? t('productLibrary.createProduct') : id);

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
          onClick={() => navigate('/home/products')}
        >
          {t('productLibrary.pageTitle')}
        </Button>
        <ChevronRight className="size-4 shrink-0" />
        <span className="font-medium text-foreground">{currentLabel}</span>
      </nav>
    );
  }

  async function saveProduct() {
    if (!draft.name.trim()) {
      toast.error(t('productLibrary.nameRequired'));
      return;
    }

    setSaving(true);
    try {
      const payload = draftToPayload(draft);
      if (isCreateMode) {
        const resp = await httpClient.createSalesProduct(payload);
        toast.success(t('productLibrary.createSuccess'));
        navigate(`/home/products?id=${encodeURIComponent(resp.uuid)}`);
        return;
      }
      await httpClient.updateSalesProduct(id, payload);
      toast.success(t('productLibrary.updateSuccess'));
      await loadProduct(id);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    try {
      await httpClient.deleteSalesProduct(id);
      setShowDeleteConfirm(false);
      toast.success(t('productLibrary.deleteSuccess'));
      navigate('/home/products');
    } catch (error) {
      toast.error(
        t('productLibrary.deleteFailed') + (error as CustomApiError).msg,
      );
    }
  }

  if (!isCreateMode && loading) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center bg-slate-50 text-sm text-slate-500">
        {t('common.loading')}
      </div>
    );
  }

  if (isCreateMode) {
    return (
      <div className="flex h-full min-h-0 flex-col bg-slate-50">
        <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
          {renderBreadcrumb(t('productLibrary.createProduct'))}
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold text-slate-950">
                {t('productLibrary.createProduct')}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {t('productLibrary.createDialogDescription')}
              </p>
            </div>
            <Button onClick={() => void saveProduct()} disabled={saving}>
              <Save className="size-4" />
              {t('productLibrary.addProduct')}
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="mx-auto max-w-4xl pb-8">
            <ProductForm draft={draft} onChange={setDraft} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex h-full min-h-0 flex-col bg-slate-50">
        <div className="shrink-0 px-6 pt-4">
          {renderBreadcrumb(displayName)}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
          <div className="mx-auto max-w-4xl space-y-4">
            <Card className="border-slate-200 bg-white shadow-none">
              <CardContent className="space-y-4 p-5">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-sky-700">
                    <Package className="size-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h1 className="truncate text-lg font-semibold text-slate-950">
                        {displayName}
                      </h1>
                      <Badge
                        variant="outline"
                        className={
                          draft.enabled
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                            : 'border-slate-200 bg-slate-50 text-slate-500'
                        }
                      >
                        {draft.enabled
                          ? t('productLibrary.statusEnabled')
                          : t('productLibrary.statusDisabled')}
                      </Badge>
                      {productInfo && isSampleProduct(productInfo) && (
                        <Badge variant="outline" className="text-slate-500">
                          {t('productLibrary.sampleBadge')}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-1 text-sm leading-6 text-slate-500">
                      {draft.description || t('productLibrary.noDescription')}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                      {draft.category && (
                        <span>
                          {t('productLibrary.categoryLabel')}: {draft.category}
                        </span>
                      )}
                      {draft.price && (
                        <span>
                          {t('productLibrary.priceLabel')}: {draft.price}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
                  <Button onClick={() => void saveProduct()} disabled={saving}>
                    <Save className="size-4" />
                    {t('productLibrary.saveChanges')}
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="gap-1.5">
                        <MoreHorizontal className="size-4" />
                        {t('productLibrary.moreActions')}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => void saveProduct()}>
                        <Pencil className="size-4" />
                        {t('productLibrary.saveChanges')}
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

            <ProductForm draft={draft} onChange={setDraft} />
          </div>
        </div>
      </div>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
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
            <Button variant="destructive" onClick={() => void confirmDelete()}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
