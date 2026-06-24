import { type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import {
  type ProductDraft,
  emptyProductDraft,
} from '@/app/home/products/utils/productUtils';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';

function FormSection({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-5 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          {icon}
          <span>{title}</span>
        </div>
      </div>
      <div className="space-y-4 p-5">{children}</div>
    </section>
  );
}

type ProductFormProps = {
  formId?: string;
  draft: ProductDraft;
  onChange: (draft: ProductDraft) => void;
};

export default function ProductForm({
  formId = 'product-form',
  draft,
  onChange,
}: ProductFormProps) {
  const { t } = useTranslation();

  const updateField = <K extends keyof ProductDraft>(
    key: K,
    value: ProductDraft[K],
  ) => {
    onChange({ ...draft, [key]: value });
  };

  return (
    <form
      id={formId}
      className="space-y-4"
      onSubmit={(event) => event.preventDefault()}
    >
      <FormSection
        icon={<span className="text-sky-600">●</span>}
        title={t('productLibrary.basicInfoSection')}
      >
        <div className="flex items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <span>{t('productLibrary.enabledLabel')}</span>
          <Switch
            checked={draft.enabled}
            onCheckedChange={(checked) => updateField('enabled', checked)}
          />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2 md:col-span-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.productLineLabel')}
            </label>
            <Input
              value={draft.product_line}
              onChange={(event) => updateField('product_line', event.target.value)}
              placeholder={t('productLibrary.productLinePlaceholder')}
            />
            <p className="text-xs text-slate-500">
              {t('productLibrary.productLineHint')}
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.nameLabel')}
            </label>
            <Input
              value={draft.name}
              onChange={(event) => updateField('name', event.target.value)}
              placeholder={t('productLibrary.namePlaceholder')}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.categoryLabel')}
            </label>
            <Input
              value={draft.category}
              onChange={(event) => updateField('category', event.target.value)}
              placeholder={t('productLibrary.categoryPlaceholder')}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.priceLabel')}
            </label>
            <Input
              value={draft.price}
              onChange={(event) => updateField('price', event.target.value)}
              placeholder={t('productLibrary.pricePlaceholder')}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.linkLabel')}
            </label>
            <Input
              value={draft.link}
              onChange={(event) => updateField('link', event.target.value)}
              placeholder={t('productLibrary.linkPlaceholder')}
            />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">
            {t('productLibrary.descriptionLabel')}
          </label>
          <Textarea
            value={draft.description}
            onChange={(event) =>
              updateField('description', event.target.value)
            }
            placeholder={t('productLibrary.descriptionPlaceholder')}
            className="min-h-24"
          />
        </div>
      </FormSection>

      <FormSection
        icon={<span className="text-emerald-600">●</span>}
        title={t('productLibrary.salesMaterialSection')}
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2 md:col-span-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.keywordsLabel')}
            </label>
            <Textarea
              value={draft.keywords}
              onChange={(event) => updateField('keywords', event.target.value)}
              placeholder={t('productLibrary.keywordsPlaceholder')}
              className="min-h-20"
            />
            <p className="text-xs text-slate-500">
              {t('productLibrary.keywordsHint')}
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.sellingPointsLabel')}
            </label>
            <Textarea
              value={draft.selling_points}
              onChange={(event) =>
                updateField('selling_points', event.target.value)
              }
              placeholder={t('productLibrary.sellingPointsPlaceholder')}
              className="min-h-28"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.painPointsLabel')}
            </label>
            <Textarea
              value={draft.pain_points}
              onChange={(event) =>
                updateField('pain_points', event.target.value)
              }
              placeholder={t('productLibrary.painPointsPlaceholder')}
              className="min-h-28"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.objectionsLabel')}
            </label>
            <Textarea
              value={draft.objections}
              onChange={(event) =>
                updateField('objections', event.target.value)
              }
              placeholder={t('productLibrary.objectionsPlaceholder')}
              className="min-h-24"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              {t('productLibrary.audienceLabel')}
            </label>
            <Textarea
              value={draft.audience}
              onChange={(event) => updateField('audience', event.target.value)}
              placeholder={t('productLibrary.audiencePlaceholder')}
              className="min-h-24"
            />
          </div>
        </div>
      </FormSection>
    </form>
  );
}

export { emptyProductDraft };
