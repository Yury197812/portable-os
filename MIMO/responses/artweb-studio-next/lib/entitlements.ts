// entitlements.ts — AutoSwitch + entitlement panel logic (PASS021 §4/§5).
//
// AutoSwitch policy: FREE first; when free quota is exhausted -> PAID_OWNED;
// unowned paid defaults to DENY. Only source-backed modes (batch/flex/cache/
// clock) are selectable — never invent off-peak discounts.

import type { Access, Entitlement } from './catalog';

export type SwitchMode = 'auto' | 'free_only' | 'paid_owned';

export interface SwitchDecision {
  ok: boolean;
  reason: string;
  chosenAccess: Access;
  chosenMode?: string;
  fallbackPath: string[];
}

// A model's entitlement is usable iff its access is FREE or PAID_OWNED.
// PAID_UNOWNED is denied unless the user explicitly owns it.
export function usableAccess(e: Entitlement): Access | null {
  if (e.access === 'FREE') return 'FREE';
  if (e.access === 'PAID_OWNED' && e.owned) return 'PAID_OWNED';
  return null; // PAID_UNOWNED or PAID_OWNED without ownership → denied
}

// Does the FREE tier still have quota? Honest: null means "unknown" (no
// source-backed number), which is treated as exhausted so we never lie "FREE available".
export function freeExhausted(e: Entitlement): boolean {
  if (e.access !== 'FREE') return true;
  if (e.freeRemaining == null) return true; // unknown → treat as exhausted (no fake availability)
  return e.freeRemaining <= 0;
}

export function decideSwitch(e: Entitlement, mode: SwitchMode = 'auto'): SwitchDecision {
  const path: string[] = [];

  if (mode === 'free_only') {
    if (e.access === 'FREE' && !freeExhausted(e)) {
      return { ok: true, reason: 'FREE available', chosenAccess: 'FREE', fallbackPath: ['FREE'] };
    }
    return { ok: false, reason: 'FREE недоступно или исчерпано (source-backed quota неизвестна)', chosenAccess: 'PAID_UNOWNED', fallbackPath: [] };
  }

  if (mode === 'paid_owned') {
    if (e.access === 'PAID_OWNED' && e.owned) {
      return { ok: true, reason: 'PAID_OWNED', chosenAccess: 'PAID_OWNED', fallbackPath: ['PAID_OWNED'] };
    }
    return { ok: false, reason: 'нет владения paid-доступом', chosenAccess: 'PAID_UNOWNED', fallbackPath: [] };
  }

  // auto: FREE first, then PAID_OWNED, unowned paid = deny
  if (e.access === 'FREE') {
    path.push('FREE');
    if (!freeExhausted(e)) {
      return { ok: true, reason: 'FREE first', chosenAccess: 'FREE', fallbackPath: path };
    }
    path.push('FREE exhausted');
    if (e.nextCheaperMode) {
      return { ok: false, reason: 'FREE исчерпан; нужен paid-режим, но доступа нет', chosenAccess: 'PAID_UNOWNED', chosenMode: e.nextCheaperMode, fallbackPath: path };
    }
    return { ok: false, reason: 'FREE исчерпан; paid не подключён', chosenAccess: 'PAID_UNOWNED', fallbackPath: path };
  }

  if (e.access === 'PAID_OWNED' && e.owned) {
    return { ok: true, reason: 'PAID_OWNED (после FREE)', chosenAccess: 'PAID_OWNED', fallbackPath: ['PAID_OWNED'] };
  }

  // PAID_UNOWNED → deny by default
  return { ok: false, reason: 'paid-доступ не принадлежит пользователю → DENY', chosenAccess: 'PAID_UNOWNED', fallbackPath: ['DENY'] };
}

// Source-backed mode list. Only these are offered; off-peak discounts are not invented.
export const SOURCE_BACKED_MODES: { id: string; label: string; note: string }[] = [
  { id: 'batch', label: 'Batch (xAI 20% только для перечисленных селекторов)', note: 'source: xAI API' },
  { id: 'flex', label: 'Flex (Groq — та же цена, не скидка)', note: 'source: Groq pricing' },
  { id: 'cache', label: 'Cache read (input cache)', note: 'source: provider pricing' },
  { id: 'clock', label: 'Clock/off-peak', note: 'source-backed только если заявлено провайдером' },
];
