// catalog.ts — единый каталог сущностей (models + agents) с provenance и
// честной классификацией доступа. PASS021: never imply global completeness,
// never mark config-only capabilities as VERIFIED, never report a configured
// provider as LIVE without a probe.

import { MODELS, type Model } from './models';
import { AGENTS, type Agent } from './agents';
import type { CapabilityId } from './capabilities';

// Provenance ladder. "DISCOVERED never implies capabilities" — capability
// claims need their own verification, not just catalog presence.
export type Provenance = 'SYNTHETIC' | 'DISCOVERED' | 'CLAIMED' | 'VERIFIED' | 'LIVE';

// Access classification. PAID_UNOWNED = a paid model the user has NOT
// connected/paid for → AutoSwitch denies by default.
export type Access = 'FREE' | 'PAID_OWNED' | 'PAID_UNOWNED';

export type CapVerification = 'CONFIG' | 'VERIFIED';

export interface Entitlement {
  access: Access;
  // free quota (only meaningful when access === 'FREE')
  freeRemaining?: number;    // e.g. requests/day remaining; source-backed or null
  freeTotal?: number;
  resetAt?: string;          // ISO; source-backed reset time
  // paid / credits (only meaningful when access !== 'FREE')
  creditsRemaining?: number;
  creditsCurrency?: string;
  owned?: boolean;           // paid access the user actually owns
  // cheaper fallback mode (AutoSwitch target)
  nextCheaperMode?: string;  // e.g. 'batch' | 'flex' | 'cache' | 'clock'
  source?: string;           // where these numbers came from; '—' = unknown
}

export type EntityKind = 'model' | 'agent';

export interface Entity {
  id: string;
  kind: EntityKind;
  name: string;
  provider: string;
  caps: CapabilityId[];
  capVerification: Record<string, CapVerification>; // per-capability verification state
  provenance: Provenance;
  free: boolean;
  entitlement: Entitlement;
  // model-only fields (agent inherits these from its backing model)
  backingModelId?: string;
  q?: number;
  lat?: number;
  cost?: number;
  ctx?: number;
  mod?: string;
}

// Real providers observed through the proxy (:8890 /api/health + /api/models).
// Only 'ollama' has a LIVE probe in this session (runtime live run, latency ~700ms).
const PROXY_LIVE: Record<string, { prov: Provenance; access: Access; caps: Record<string, CapVerification> }> = {
  // ollama: real live probe (runtime run returned content) → LIVE/VERIFIED
  'qwen2.5:14b': { prov: 'LIVE', access: 'FREE', caps: { tool_use: 'VERIFIED', code: 'CONFIG', free: 'VERIFIED', speed: 'VERIFIED' } },
  // configured in proxy but no key/probe this session → DISCOVERED, not routing-ready
  'llama-3.3-70b-versatile': { prov: 'DISCOVERED', access: 'PAID_UNOWNED', caps: { tool_use: 'CONFIG', reasoning: 'CONFIG' } },
  'llama-3.1-8b-instant': { prov: 'DISCOVERED', access: 'PAID_UNOWNED', caps: { tool_use: 'CONFIG', speed: 'CONFIG' } },
  'openai/gpt-oss-20b:free': { prov: 'DISCOVERED', access: 'FREE', caps: { tool_use: 'CONFIG', code: 'CONFIG' } },
  'google/gemma-4-26b-a4b-it:free': { prov: 'DISCOVERED', access: 'FREE', caps: { tool_use: 'CONFIG' } },
  'liquid/lfm-2.5-2.6b:free': { prov: 'DISCOVERED', access: 'FREE', caps: { speed: 'CONFIG' } },
  'nvidia/nemotron-nano-9b-v2:free': { prov: 'DISCOVERED', access: 'FREE', caps: { tool_use: 'CONFIG' } },
};

// Official source registry (PASS021 §7). Anything NOT in this map is UNVERIFIED
// for deal/connection radar purposes.
export const OFFICIAL_SOURCES: Record<string, string> = {
  OpenAI: 'https://openai.com/api/pricing/',
  Anthropic: 'https://www.anthropic.com/pricing',
  Gemini: 'https://ai.google.dev/pricing',
  OpenRouter: 'https://openrouter.ai/models',
  Groq: 'https://groq.com/pricing',
  Mistral: 'https://mistral.ai/pricing',
  xAI: 'https://x.ai/api',
};

function capVerMap(caps: CapabilityId[]): Record<string, CapVerification> {
  const out: Record<string, CapVerification> = {};
  for (const c of caps) out[c] = 'CONFIG'; // config-only unless a probe verified it
  return out;
}

function buildModelEntity(m: Model): Entity {
  const live = PROXY_LIVE[m.id];
  const free = m.free;
  const access: Access = live ? live.access : free ? 'FREE' : 'PAID_UNOWNED';
  return {
    id: m.id,
    kind: 'model',
    name: m.name,
    provider: m.provider,
    caps: m.caps,
    capVerification: live ? { ...capVerMap(m.caps), ...live.caps } : capVerMap(m.caps),
    provenance: live ? live.prov : 'SYNTHETIC',
    free,
    entitlement: {
      access,
      owned: access === 'PAID_OWNED',
      // free quota numbers are NOT source-backed for seed data → leave null
      source: live ? 'proxy :8890' : 'seed (SYNTHETIC)',
    },
    q: m.q,
    lat: m.lat,
    cost: m.cost,
    ctx: m.ctx,
    mod: m.mod,
  };
}

function buildAgentEntity(a: Agent): Entity {
  // Agents inherit provider/free/capability truth from their backing model
  // when model_policy points to it (PASS021 §3). Config-only caps stay CONFIG.
  const backing = MODELS.find((m) => m.name === a.model);
  const inheritedCaps: CapabilityId[] = backing ? backing.caps : [];
  const mergedCaps = Array.from(new Set<CapabilityId>([...inheritedCaps, ...a.caps]));
  const ver = capVerMap(mergedCaps);
  // only caps verified on the backing model (via a live probe) become VERIFIED
  const live = backing ? PROXY_LIVE[backing.id] : undefined;
  if (live) for (const [c, s] of Object.entries(live.caps)) if (s === 'VERIFIED' && c in ver) ver[c] = 'VERIFIED';

  return {
    id: `agent-${a.n.replace(/\s+/g, '-').toLowerCase()}`,
    kind: 'agent',
    name: a.n,
    provider: backing ? backing.provider : '—',
    caps: mergedCaps,
    capVerification: ver,
    provenance: backing ? (live ? live.prov : 'SYNTHETIC') : 'SYNTHETIC',
    free: backing ? backing.free : false,
    entitlement: backing
      ? { access: backing.free ? 'FREE' : 'PAID_UNOWNED', owned: false, source: 'inherited from backing model' }
      : { access: 'PAID_UNOWNED', owned: false, source: '—' },
    backingModelId: backing ? backing.id : undefined,
  };
}

export const MODEL_ENTITIES: Entity[] = MODELS.map(buildModelEntity);
export const AGENT_ENTITIES: Entity[] = AGENTS.map(buildAgentEntity);

// ALL = all entities from all currently observed sources (models + agents).
// Coverage status is local (seed + proxy), never "the whole internet".
export const ALL_ENTITIES: Entity[] = [...MODEL_ENTITIES, ...AGENT_ENTITIES];

// ---- filtering: PASS021 §2 — filters are AND (not OR) ----

export interface CatalogFilter {
  kinds: Set<EntityKind>;         // empty = all kinds
  caps: Set<CapabilityId>;        // AND across these capabilities
  free: boolean | null;           // null = no free filter
  access: Set<Access>;            // empty = all access classes
}

export function applyFilter(entities: Entity[], f: CatalogFilter): Entity[] {
  return entities.filter((e) => {
    if (f.kinds.size && !f.kinds.has(e.kind)) return false;
    if (f.caps.size && ![...f.caps].every((c) => e.caps.includes(c))) return false;
    if (f.free !== null && e.free !== f.free) return false;
    if (f.access.size && !f.access.has(e.entitlement.access)) return false;
    return true;
  });
}

// Split into primary (FREE) and PAID·OWNED blocks per PASS021 §2.
export function splitBlocks(entities: Entity[]): { primary: Entity[]; paidOwned: Entity[] } {
  const primary: Entity[] = [];
  const paidOwned: Entity[] = [];
  for (const e of entities) {
    if (e.entitlement.access === 'PAID_OWNED') paidOwned.push(e);
    else primary.push(e);
  }
  return { primary, paidOwned };
}

export function coverageStatus(entities: Entity[]): { total: number; models: number; agents: number; free: number; paidOwned: number; scope: string } {
  return {
    total: entities.length,
    models: entities.filter((e) => e.kind === 'model').length,
    agents: entities.filter((e) => e.kind === 'agent').length,
    free: entities.filter((e) => e.entitlement.access === 'FREE').length,
    paidOwned: entities.filter((e) => e.entitlement.access === 'PAID_OWNED').length,
    scope: 'local seed + proxy :8890 (не весь интернет)',
  };
}
