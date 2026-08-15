// deals.ts — Official Deal / Connection Radar (PASS021 §6/§7).
//
// Only an exact official source can be VERIFIED. Third-party / user ads stay
// UNVERIFIED until explicit evidence. Official-source registry:
// OpenAI / Anthropic / Gemini / OpenRouter / Groq / Mistral / xAI.
// xAI 20% batch applies ONLY to the listed model selectors; Groq Flex is the
// SAME price, not a discount.

import { OFFICIAL_SOURCES } from './catalog';

export type DealStatus = 'VERIFIED' | 'UNVERIFIED';

export interface Deal {
  id: string;
  provider: string;
  title: string;
  kind: 'discount' | 'connection' | 'free_tier';
  detail: string;
  status: DealStatus;
  source: string; // exact URL if VERIFIED, else '—'
  reason?: string; // why UNVERIFIED
  appliesTo?: string[]; // exact selectors when the deal is scoped
}

// Hard-coded xAI batch discount selectors — the ONLY models the 20% applies to.
// (Kept explicit so we never claim the discount on unlisted selectors.)
const XAI_BATCH_20_SELECTORS = ['grok-beta', 'grok-2', 'grok-2-mini'];

const DEALS: Deal[] = [
  {
    id: 'xai-batch-20',
    provider: 'xAI',
    title: 'Batch API −20%',
    kind: 'discount',
    detail: '20% скидка на batch-запросы, только для перечисленных селекторов.',
    status: 'VERIFIED',
    source: OFFICIAL_SOURCES.xAI,
    appliesTo: XAI_BATCH_20_SELECTORS,
  },
  {
    id: 'groq-flex',
    provider: 'Groq',
    title: 'Flex tier',
    kind: 'free_tier',
    detail: 'Groq Flex — та же цена, НЕ скидка (не является дисконтом).',
    status: 'VERIFIED',
    source: OFFICIAL_SOURCES.Groq,
  },
  {
    id: 'openrouter-free',
    provider: 'OpenRouter',
    title: 'Free модели (:free)',
    kind: 'free_tier',
    detail: 'Модели с суффиксом :free доступны без оплаты (rate-limited).',
    status: 'VERIFIED',
    source: OFFICIAL_SOURCES.OpenRouter,
  },
  {
    id: 'user-deal-sample',
    provider: 'Unknown',
    title: 'Пример стороннего объявления',
    kind: 'discount',
    detail: '«Скидка 50% на все модели» — стороннее/пользовательское объявление.',
    status: 'UNVERIFIED',
    source: '—',
    reason: 'нет официального источника; остаётся UNVERIFIED до явного доказательства',
  },
];

export function dealRadar(): Deal[] {
  return DEALS;
}

// Is a specific deal allowed for a given model selector?
export function dealApplies(deal: Deal, modelSelector: string): boolean {
  if (!deal.appliesTo) return true; // unscoped deal
  return deal.appliesTo.includes(modelSelector);
}

export const OFFICIAL_REGISTRY = Object.keys(OFFICIAL_SOURCES);
