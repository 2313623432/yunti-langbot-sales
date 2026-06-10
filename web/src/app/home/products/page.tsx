import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Package, Plus, Search } from 'lucide-react';
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

  const pageCount = Math.max(
    1,
    Math.ceil(filteredProducts.length / PAGE_SIZE),
  );
  const safePage = Math.min(page, pageCount);
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
