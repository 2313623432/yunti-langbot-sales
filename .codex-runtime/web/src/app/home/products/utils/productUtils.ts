import { SalesProduct } from '@/app/infra/entities/api';

export const DEFAULT_PRODUCT_UUIDS = new Set([
  'sales-ai-assistant',
  'product-knowledge-base',
]);

export type ProductDraft = {
  name: string;
  product_line: string;
  profile_key: string;
  keywords: string;
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

export const emptyProductDraft: ProductDraft = {
  name: '',
  product_line: '',
  profile_key: '',
  keywords: '',
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

export const splitList = (value: string): string[] =>
  value
    .split(/[\n,，;；]/)
    .map((item) => item.trim())
    .filter(Boolean);

export const joinList = (value?: string[]): string => (value || []).join('\n');

export const errorMessage = (error: unknown): string => {
  if (error && typeof error === 'object' && 'msg' in error) {
    return String((error as { msg?: string }).msg);
  }
  if (error instanceof Error) return error.message;
  return 'Request failed';
};

export function hasCustomSalesProduct(products: SalesProduct[]): boolean {
  return products.some(
    (product) => product.uuid && !DEFAULT_PRODUCT_UUIDS.has(product.uuid),
  );
}

export function productToDraft(product: SalesProduct): ProductDraft {
  return {
    name: product.name,
    product_line: product.product_line || '',
    profile_key: product.profile_key || '',
    keywords: joinList(product.keywords),
    category: product.category,
    price: product.price,
    link: product.link,
    description: product.description,
    selling_points: joinList(product.selling_points),
    pain_points: joinList(product.pain_points),
    objections: joinList(product.objections),
    audience: joinList(product.audience),
    enabled: product.enabled,
  };
}

export function draftToPayload(draft: ProductDraft) {
  return {
    name: draft.name.trim(),
    product_line: draft.product_line.trim(),
    profile_key: draft.profile_key.trim(),
    keywords: splitList(draft.keywords),
    category: draft.category.trim(),
    price: draft.price.trim(),
    link: draft.link.trim(),
    description: draft.description.trim(),
    selling_points: splitList(draft.selling_points),
    pain_points: splitList(draft.pain_points),
    objections: splitList(draft.objections),
    audience: splitList(draft.audience),
    enabled: draft.enabled,
  };
}

export function isSampleProduct(product: SalesProduct): boolean {
  return Boolean(product.uuid && DEFAULT_PRODUCT_UUIDS.has(product.uuid));
}
