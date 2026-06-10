import { type ReactNode, useEffect, useState } from 'react';
import { PackagePlus, RefreshCw, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { SalesProduct } from '@/app/infra/entities/api';
import { httpClient, initializeUserInfo } from '@/app/infra/http';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';

export const DEFAULT_PRODUCT_UUIDS = new Set([
  'sales-ai-assistant',
  'product-knowledge-base',
]);

type ProductDraft = {
  name: string;
  category: string;
  price: string;
  link: string;
  description: string;
  selling_points: string;
  pain_points: string;
  objections: string;
  audience: string;
  enabled: boolean;
};

const emptyProduct: ProductDraft = {
  name: '',
  category: '',
  price: '',
  link: '',
  description: '',
  selling_points: '',
  pain_points: '',
  objections: '',
  audience: '',
  enabled: true,
};

const splitList = (value: string): string[] =>
  value
    .split(/[\n,，;；]/)
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (value?: string[]): string => (value || []).join('\n');

const errorMessage = (error: unknown): string => {
  if (error && typeof error === 'object' && 'msg' in error) {
    return String((error as { msg?: string }).msg);
  }
  if (error instanceof Error) return error.message;
  return '请求失败';
};

export function hasCustomSalesProduct(products: SalesProduct[]): boolean {
  return products.some(
    (product) => product.uuid && !DEFAULT_PRODUCT_UUIDS.has(product.uuid),
  );
}

function SectionTitle({
  icon,
  title,
  action,
  subtitle,
}: {
  icon: ReactNode;
  title: string;
  action?: React.ReactNode;
  subtitle?: string;
}) {
  return (
    <div className="border-b border-slate-200 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="rounded-md bg-slate-100 p-2 text-slate-700">
            {icon}
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-950">
              {title}
            </h2>
            {subtitle && (
              <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
            )}
          </div>
        </div>
        {action}
      </div>
    </div>
  );
}

type ProductLibraryManagerProps = {
  sectionId?: string;
  showHeader?: boolean;
  onProductsChange?: (products: SalesProduct[]) => void;
};

export default function ProductLibraryManager({
  sectionId = 'product-library-section',
  showHeader = true,
  onProductsChange,
}: ProductLibraryManagerProps) {
  const { t } = useTranslation();
  const [products, setProducts] = useState<SalesProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingProduct, setSavingProduct] = useState(false);
  const [editingUuid, setEditingUuid] = useState<string | null>(null);
  const [productDraft, setProductDraft] = useState<ProductDraft>(emptyProduct);

  const loadProducts = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      await initializeUserInfo();
      const productResp = await httpClient.getSalesProducts();
      const nextProducts = productResp.products || [];
      setProducts(nextProducts);
      onProductsChange?.(nextProducts);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    void loadProducts();
  }, []);

  const updateProductDraft = (
    key: keyof ProductDraft,
    value: string | boolean,
  ) => {
    setProductDraft((draft) => ({ ...draft, [key]: value }));
  };

  const saveProduct = async () => {
    if (!productDraft.name.trim()) {
      toast.error(t('productLibrary.nameRequired'));
      return;
    }
    setSavingProduct(true);
    try {
      const payload = {
        name: productDraft.name.trim(),
        category: productDraft.category.trim(),
        price: productDraft.price.trim(),
        link: productDraft.link.trim(),
        description: productDraft.description.trim(),
        selling_points: splitList(productDraft.selling_points),
        pain_points: splitList(productDraft.pain_points),
        objections: splitList(productDraft.objections),
        audience: splitList(productDraft.audience),
        enabled: productDraft.enabled,
      };
      if (editingUuid) {
        await httpClient.updateSalesProduct(editingUuid, payload);
        toast.success(t('productLibrary.updateSuccess'));
      } else {
        await httpClient.createSalesProduct(payload);
        toast.success(t('productLibrary.createSuccess'));
      }
      setEditingUuid(null);
      setProductDraft(emptyProduct);
      await loadProducts(false);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSavingProduct(false);
    }
  };

  const editProduct = (product: SalesProduct) => {
    setEditingUuid(product.uuid || null);
    setProductDraft({
      name: product.name,
      category: product.category,
      price: product.price,
      link: product.link,
      description: product.description,
      selling_points: joinList(product.selling_points),
      pain_points: joinList(product.pain_points),
      objections: joinList(product.objections),
      audience: joinList(product.audience),
      enabled: product.enabled,
    });
    document
      .getElementById(sectionId)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const deleteProduct = async (product: SalesProduct) => {
    if (!product.uuid) return;
    try {
      await httpClient.deleteSalesProduct(product.uuid);
      await loadProducts(false);
      toast.success(t('productLibrary.deleteSuccess'));
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  return (
    <section
      id={sectionId}
      className="rounded-lg border border-slate-200 bg-white shadow-sm"
    >
      {showHeader && (
        <SectionTitle
          icon={<PackagePlus className="size-4" />}
          title={t('productLibrary.sectionTitle')}
          subtitle={t('productLibrary.sectionSubtitle')}
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => void loadProducts()}
            >
              <RefreshCw className="size-4" />
              {t('common.refresh')}
            </Button>
          }
        />
      )}
      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2 text-sm text-slate-600">
            <span>{t('productLibrary.enabledLabel')}</span>
            <Switch
              checked={productDraft.enabled}
              onCheckedChange={(checked) =>
                updateProductDraft('enabled', checked)
              }
            />
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Input
              value={productDraft.name}
              onChange={(event) =>
                updateProductDraft('name', event.target.value)
              }
              placeholder={t('productLibrary.namePlaceholder')}
            />
            <Input
              value={productDraft.category}
              onChange={(event) =>
                updateProductDraft('category', event.target.value)
              }
              placeholder={t('productLibrary.categoryPlaceholder')}
            />
            <Input
              value={productDraft.price}
              onChange={(event) =>
                updateProductDraft('price', event.target.value)
              }
              placeholder={t('productLibrary.pricePlaceholder')}
            />
            <Input
              value={productDraft.link}
              onChange={(event) =>
                updateProductDraft('link', event.target.value)
              }
              placeholder={t('productLibrary.linkPlaceholder')}
            />
          </div>
          <Textarea
            value={productDraft.description}
            onChange={(event) =>
              updateProductDraft('description', event.target.value)
            }
            placeholder={t('productLibrary.descriptionPlaceholder')}
            className="min-h-20"
          />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Textarea
              value={productDraft.selling_points}
              onChange={(event) =>
                updateProductDraft('selling_points', event.target.value)
              }
              placeholder={t('productLibrary.sellingPointsPlaceholder')}
              className="min-h-28"
            />
            <Textarea
              value={productDraft.pain_points}
              onChange={(event) =>
                updateProductDraft('pain_points', event.target.value)
              }
              placeholder={t('productLibrary.painPointsPlaceholder')}
              className="min-h-28"
            />
            <Textarea
              value={productDraft.objections}
              onChange={(event) =>
                updateProductDraft('objections', event.target.value)
              }
              placeholder={t('productLibrary.objectionsPlaceholder')}
              className="min-h-24"
            />
            <Textarea
              value={productDraft.audience}
              onChange={(event) =>
                updateProductDraft('audience', event.target.value)
              }
              placeholder={t('productLibrary.audiencePlaceholder')}
              className="min-h-24"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={saveProduct} disabled={savingProduct}>
              <Save className="size-4" />
              {editingUuid
                ? t('productLibrary.saveChanges')
                : t('productLibrary.addProduct')}
            </Button>
            {editingUuid && (
              <Button
                variant="outline"
                onClick={() => {
                  setEditingUuid(null);
                  setProductDraft(emptyProduct);
                }}
              >
                {t('common.cancel')}
              </Button>
            )}
          </div>
        </div>

        <div className="min-h-[360px] overflow-hidden rounded-lg border border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-2">
            <span className="text-sm font-medium text-slate-700">
              {t('productLibrary.listTitle')}
            </span>
            {loading && (
              <Badge variant="outline" className="text-slate-500">
                {t('common.loading')}
              </Badge>
            )}
          </div>
          <div className="max-h-[520px] divide-y divide-slate-200 overflow-auto">
            {products.map((product) => (
              <div key={product.uuid || product.name} className="p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-semibold text-slate-950">
                        {product.name}
                      </p>
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
                      {product.uuid &&
                        DEFAULT_PRODUCT_UUIDS.has(product.uuid) && (
                          <Badge variant="outline" className="text-slate-500">
                            {t('productLibrary.sampleBadge')}
                          </Badge>
                        )}
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-slate-600">
                      {product.description || t('productLibrary.noDescription')}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
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
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => editProduct(product)}
                    >
                      {t('common.edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteProduct(product)}
                    >
                      {t('common.delete')}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
            {!products.length && !loading && (
              <div className="p-6 text-center text-sm text-slate-500">
                {t('productLibrary.emptyList')}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
