import { useTranslation } from 'react-i18next';
import { Package } from 'lucide-react';

import ProductLibraryManager from '@/app/home/products/components/ProductLibraryManager';

export default function ProductsPage() {
  const { t } = useTranslation();

  return (
    <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain bg-[#f6f5ef] p-3 text-slate-900 sm:p-4">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-3 sm:gap-4">
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex flex-wrap items-center gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-1 text-sm font-medium text-sky-700">
                <Package className="size-4" />
                <span>{t('sidebar.productLibrary')}</span>
              </div>
              <h1 className="text-2xl font-semibold text-slate-950 sm:text-3xl">
                {t('productLibrary.pageTitle')}
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                {t('productLibrary.pageDescription')}
              </p>
            </div>
          </div>
        </section>

        <ProductLibraryManager />
      </div>
    </div>
  );
}
