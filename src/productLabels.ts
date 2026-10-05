import type { CardKind } from './types';

export function cardLabelKey(card: { cardKind?: CardKind | null }, fallback = 'card') {
  return card.cardKind === 'credit' ? 'creditCard' : card.cardKind === 'debit' ? 'debitCard' : fallback;
}

export function productLabelKey(product: { type: string; cardKind?: CardKind | null }) {
  return product.type === 'card' ? cardLabelKey(product) : product.type;
}
