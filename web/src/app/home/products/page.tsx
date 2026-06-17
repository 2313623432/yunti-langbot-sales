import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Package,
  Plus,
  Search,
} from 'lucide-react';
import { toast } from 'sonner';

import ProductDetailContent from '@/app/home/products/ProductDetailContent';
import ProductCard from '@/app/home/products/components/product-card/ProductCard';
import { groupProductsByLine } from '@/app/home/products/utils/productLineUtils';
import { errorMessage } from '@/app/home/products/utils/productUtils';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { SalesProduct } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
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

const PAGE_SIZE = 9;

type ProductAiReferenceCheck = {
  key: string;
  label: string;
  isComplete: (product: SalesProduct) => boolean;
};

const AI_REFERENCE_CHECKS: ProductAiReferenceCheck[] = [
  {
    key: 'enabled',
    label: '启用',
    isComplete: (product) => product.enabled,
  },
  {
    key: 'description',
    label: '描述',
    isComplete: (product) => Boolean(product.description?.trim()),
  },
  {
    key: 'selling_points',
    label: '卖点',
    isComplete: (product) => (product.selling_points || []).length > 0,
  },
  {
    key: 'price',
    label: '价格',
    isComplete: (product) => Boolean(product.price?.trim()),
  },
  {
    key: 'category',
    label: '分类',
    isComplete: (product) => Boolean(product.category?.trim()),
  },
];

function getProductAiReferenceStatus(product: SalesProduct) {
  const missingChecks = AI_REFERENCE_CHECKS.filter(
    (check) => !check.isComplete(product),
  );

  return {
    product,
    completedCount: AI_REFERENCE_CHECKS.length - missingChecks.length,
    missingLabels: missingChecks.map((check) => check.label),
    ready: missingChecks.length === 0,
  };
}

export default function ProductsPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');
  const navigate = useNavigate();
  const { setDetailEntityName } = useSidebarData();

  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [products, setProducts] = useState<SalesProduct[]>([]);
  const [loading, setLoading] = useState(true);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const resp = await httpClient.getSalesProducts();
      setProducts(resp.products || []);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!detailId) {
      setDetailEntityName(null);
      void loadProducts();
    }
  }, [detailId, setDetailEntityName]);

  const filteredProducts = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    if (!normalizedKeyword) return products;

    return products.filter((product) => {
      return [
        product.name,
        product.product_line,
        product.category,
        product.description,
        product.price,
        ...(product.selling_points || []),
        ...(product.keywords || []),
      ]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(normalizedKeyword));
    });
  }, [keyword, products]);

  const pageCount = Math.max(1, Math.ceil(filteredProducts.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const aiReferenceSummary = useMemo(() => {
    const statuses = filteredProducts.map(getProductAiReferenceStatus);
    const totalChecks = statuses.length * AI_REFERENCE_CHECKS.length;
    const completedChecks = statuses.reduce(
      (total, status) => total + status.completedCount,
      0,
    );
    const readyCount = statuses.filter((status) => status.ready).length;
    const missingStats = AI_REFERENCE_CHECKS.map((check) => ({
      key: check.key,
      label: check.label,
      count: filteredProducts.filter((product) => !check.isComplete(product))
        .length,
    }));
    const priorityProducts = statuses
      .filter((status) => !status.ready)
      .sort((left, right) => left.completedCount - right.completedCount)
      .slice(0, 3);

    return {
      readyCount,
      totalCount: statuses.length,
      score: totalChecks
        ? Math.round((completedChecks / totalChecks) * 100)
        : 0,
      missingStats,
      priorityProducts,
    };
  }, [filteredProducts]);
  const productLineGroups = useMemo(
    () => groupProductsByLine(filteredProducts),
    [filteredProducts],
  );
  const visibleProducts = filteredProducts.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );
  const visibleGroups = useMemo(() => {
    const visibleIds = new Set(
      visibleProducts.map((product) => product.uuid || product.name),
    );
    return productLineGroups
      .map((group) => ({
        ...group,
        products: group.products.filter((product) =>
          visibleIds.has(product.uuid || product.name),
        ),
      }))
      .filter((group) => group.products.length > 0);
  }, [productLineGroups, visibleProducts]);

  useEffect(() => {
    setPage(1);
  }, [keyword, products.length]);

  if (detailId) {
    return <ProductDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-50 text-slate-900">
      <div className="shrink-0 px-6 pb-5 pt-4">
        <div className="mb-4">
          <h1 className="text-2xl font-semibold text-slate-950">
            {t('productLibrary.pageTitle')}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            {t('productLibrary.pageDescription')}
          </p>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full sm:max-w-md">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              className="h-11 border-slate-200 bg-white pl-9 text-sm"
              placeholder={t('productLibrary.searchPlaceholder')}
            />
          </div>
          <Button
            className="h-11 px-6"
            onClick={() => navigate('/home/products?id=new')}
          >
            <Plus className="size-4" />
            {t('productLibrary.createProduct')}
          </Button>
        </div>

        <section className="mt-5 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
                  <Bot className="size-5" />
                </span>
                <div>
                  <h2 className="text-base font-semibold text-slate-950">
                    AI 可用性 / 销售智能体可引用度
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    检查产品是否已补齐描述、卖点、价格和分类，避免智能体回答销售问题时缺少依据。
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 xl:min-w-[520px]">
              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                <p className="text-xs text-slate-500">整体引用度</p>
                <div className="mt-2 flex items-end gap-2">
                  <span className="text-2xl font-semibold text-slate-950">
                    {aiReferenceSummary.score}%
                  </span>
                  <span className="pb-1 text-xs text-slate-500">
                    {aiReferenceSummary.totalCount} 个产品
                  </span>
                </div>
                <div className="mt-3 h-1.5 rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-indigo-600"
                    style={{ width: `${aiReferenceSummary.score}%` }}
                  />
                </div>
              </div>

              <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                <div className="flex items-center gap-2 text-emerald-700">
                  <CheckCircle2 className="size-4" />
                  <p className="text-xs font-medium">可直接引用</p>
                </div>
                <p className="mt-2 text-2xl font-semibold text-emerald-800">
                  {aiReferenceSummary.readyCount}
                </p>
                <p className="mt-1 text-xs text-emerald-700">
                  已启用且核心销售资料完整
                </p>
              </div>

              <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                <div className="flex items-center gap-2 text-amber-700">
                  <AlertTriangle className="size-4" />
                  <p className="text-xs font-medium">待补齐</p>
                </div>
                <p className="mt-2 text-2xl font-semibold text-amber-800">
                  {Math.max(
                    aiReferenceSummary.totalCount -
                      aiReferenceSummary.readyCount,
                    0,
                  )}
                </p>
                <p className="mt-1 text-xs text-amber-700">
                  缺少启用状态或关键销售字段
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
            <div className="flex flex-wrap gap-2">
              {aiReferenceSummary.missingStats.map((item) => (
                <span
                  key={item.key}
                  className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600"
                >
                  <span>{item.label}</span>
                  <span
                    className={
                      item.count
                        ? 'font-semibold text-amber-700'
                        : 'font-semibold text-emerald-700'
                    }
                  >
                    缺 {item.count}
                  </span>
                </span>
              ))}
            </div>

            <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
              <p className="text-sm font-medium text-slate-900">优先补齐</p>
              {aiReferenceSummary.priorityProducts.length > 0 ? (
                <div className="mt-2 space-y-2">
                  {aiReferenceSummary.priorityProducts.map((status) => (
                    <button
                      key={status.product.uuid || status.product.name}
                      type="button"
                      disabled={!status.product.uuid}
                      className="block w-full rounded-md bg-white px-3 py-2 text-left text-sm transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                      onClick={() => {
                        if (!status.product.uuid) return;
                        navigate(
                          `/home/products?id=${encodeURIComponent(status.product.uuid)}`,
                        );
                      }}
                    >
                      <span className="block truncate font-medium text-slate-950">
                        {status.product.name}
                      </span>
                      <span className="mt-1 block truncate text-xs text-slate-500">
                        {status.product.uuid
                          ? `缺少：${status.missingLabels.join('、')}`
                          : '保存产品后可进入详情补齐'}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-500">
                  当前筛选结果里的产品都已满足基础引用条件。
                </p>
              )}
            </div>
          </div>
        </section>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-5">
        {loading ? (
          <div className="flex h-full min-h-[360px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white text-sm text-slate-500">
            {t('common.loading')}
          </div>
        ) : visibleProducts.length > 0 ? (
          <div className="space-y-8">
            {visibleGroups.map((group) => (
              <section key={group.line} className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">
                      {group.line}
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">
                      {t('productLibrary.productLineCount', {
                        count: group.products.length,
                      })}
                    </p>
                  </div>
                </div>
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                  {group.products.map((product) => (
                    <ProductCard
                      key={product.uuid || product.name}
                      product={product}
                      onClick={() =>
                        navigate(
                          `/home/products?id=${encodeURIComponent(product.uuid || '')}`,
                        )
                      }
                      onDeleted={loadProducts}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="flex h-full min-h-[360px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white">
            <div className="flex max-w-sm flex-col items-center gap-3 text-center">
              <div className="flex size-12 items-center justify-center rounded-full bg-sky-50 text-sky-600">
                <Package className="size-6" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  {t('productLibrary.emptyListTitle')}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {t('productLibrary.emptyListDescription')}
                </p>
              </div>
              <Button onClick={() => navigate('/home/products?id=new')}>
                <Plus className="size-4" />
                {t('productLibrary.createProduct')}
              </Button>
            </div>
          </div>
        )}
      </div>

      {filteredProducts.length > PAGE_SIZE && (
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
  );
}
