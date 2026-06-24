import { SalesProduct } from '@/app/infra/entities/api';

export const UNGROUPED_PRODUCT_LINE = '未分组';

export type ProductLineGroup = {
  line: string;
  products: SalesProduct[];
};

export function resolveProductLine(product: SalesProduct): string {
  const line = product.product_line?.trim();
  return line || UNGROUPED_PRODUCT_LINE;
}

export function groupProductsByLine(products: SalesProduct[]): ProductLineGroup[] {
  const groups = new Map<string, SalesProduct[]>();

  for (const product of products) {
    const line = resolveProductLine(product);
    const bucket = groups.get(line) || [];
    bucket.push(product);
    groups.set(line, bucket);
  }

  return Array.from(groups.entries())
    .map(([line, lineProducts]) => ({
      line,
      products: lineProducts.sort((left, right) =>
        left.name.localeCompare(right.name, 'zh-Hans'),
      ),
    }))
    .sort((left, right) => {
      if (left.line === UNGROUPED_PRODUCT_LINE) return 1;
      if (right.line === UNGROUPED_PRODUCT_LINE) return -1;
      return left.line.localeCompare(right.line, 'zh-Hans');
    });
}
