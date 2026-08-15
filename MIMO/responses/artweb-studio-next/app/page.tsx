'use client';

import { useMemo, useState } from 'react';
import { ALL_ENTITIES, applyFilter, splitBlocks, coverageStatus, type Entity, type CatalogFilter } from '@/lib/catalog';
import { CAPS, type CapabilityId } from '@/lib/capabilities';
import { decideSwitch, type SwitchMode, SOURCE_BACKED_MODES } from '@/lib/entitlements';
import { dealRadar, OFFICIAL_REGISTRY } from '@/lib/deals';

const RUNTIME = 'http://127.0.0.1:8891';

function EntityCard({ e }: { e: Entity }) {
  const provColor: Record<string, string> = {
    LIVE: 'var(--emerald)',
    VERIFIED: 'var(--emerald)',
    DISCOVERED: 'var(--amber)',
    CLAIMED: 'var(--cyan)',
    SYNTHETIC: 'var(--text3)',
  };
  const accessBadge =
    e.entitlement.access === 'FREE' ? (
      <span className="badge">FREE</span>
    ) : e.entitlement.access === 'PAID_OWNED' ? (
      <span className="badge" style={{ background: 'rgba(124,58,237,.16)', color: 'var(--accent2)', borderColor: 'rgba(124,58,237,.35)' }}>PAID·OWNED</span>
    ) : (
      <span className="badge" style={{ background: 'rgba(251,113,133,.14)', color: 'var(--rose)', borderColor: 'rgba(251,113,133,.3)' }}>PAID·UNOWNED</span>
    );

  const ver = e.capVerification;
  return (
    <div className="mcard">
      <div className="top">
        <div>
          <div className="name">
            {e.name}{' '}
            <span style={{ fontSize: 10, color: 'var(--text3)', fontWeight: 400 }}>
              {e.kind === 'agent' ? 'агент' : ''}
            </span>
          </div>
          <div className="provider">{e.provider} · {e.kind === 'model' ? e.mod : `backing: ${e.backingModelId ?? '—'}`}</div>
        </div>
        {accessBadge}
      </div>
      <div className="caps">
        {e.caps.map((c) => {
          const verified = ver[c] === 'VERIFIED';
          return (
            <span
              key={c}
              className="cap"
              title={verified ? 'VERIFIED (живая проба)' : 'CONFIG (не проверено прогоном)'}
              style={{
                color: verified ? 'var(--emerald)' : 'var(--text2)',
                borderColor: verified ? 'rgba(52,211,153,.4)' : 'var(--border)',
                background: verified ? 'rgba(52,211,153,.1)' : 'transparent',
              }}
            >
              {verified ? '✓ ' : ''}{CAPS[c]?.label ?? c}
            </span>
          );
        })}
      </div>
      <div className="meta">
        {e.kind === 'model' && e.q != null && <span><b>Q</b> {e.q}/10</span>}
        {e.kind === 'model' && e.lat != null && <span><b>Lat</b> {e.lat}ms</span>}
        {e.kind === 'model' && e.cost != null && <span><b>Cost</b> {e.cost ? `$${e.cost}` : '0'}</span>}
        <span><b>Prov</b> <span style={{ color: provColor[e.provenance] }}>{e.provenance}</span></span>
      </div>
    </div>
  );
}

function EntitlementPanel() {
  const [selId, setSelId] = useState('gpt-4o-mini');
  const [mode, setMode] = useState<SwitchMode>('auto');
  const [apiDecision, setApiDecision] = useState<string | null>(null);
  const [apiRunId, setApiRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const e = ALL_ENTITIES.find((x) => x.id === selId) ?? ALL_ENTITIES[0];
  const d = decideSwitch(e.entitlement, mode);

  // UI acceptance (PASS021 §8): click -> API call -> runtime state/readback.
  const runSwitch = async () => {
    setBusy(true);
    setApiDecision(null);
    try {
      const r = await fetch(`${RUNTIME}/api/autoswitch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          access: e.entitlement.access,
          owned: e.entitlement.owned,
          free_remaining: e.entitlement.freeRemaining ?? null,
        }),
      });
      const j = await r.json();
      // readback the durable decision
      const rb = await fetch(`${RUNTIME}/api/autoswitch/${j.run_id}`).then((x) => x.json());
      setApiRunId(j.run_id);
      setApiDecision(`${rb.decision?.chosen}: ${rb.decision?.reason}`);
    } catch (err) {
      setApiDecision(`ошибка соединения: ${err}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 10px', fontFamily: 'var(--head)', fontSize: 14 }}>Entitlement + AutoSwitch</h3>
      <div className="toolbar" style={{ marginBottom: 10 }}>
        <select className="cmp-select" value={selId} onChange={(ev) => setSelId(ev.target.value)} aria-label="Сущность для AutoSwitch">
          {ALL_ENTITIES.map((x) => (
            <option key={x.id} value={x.id}>{x.name} ({x.entitlement.access})</option>
          ))}
        </select>
        <select className="cmp-select" value={mode} onChange={(ev) => setMode(ev.target.value as SwitchMode)} aria-label="Режим AutoSwitch">
          <option value="auto">auto (FREE → PAID_OWNED → deny)</option>
          <option value="free_only">только FREE</option>
          <option value="paid_owned">только PAID_OWNED</option>
        </select>
        <button className="btn" onClick={runSwitch} disabled={busy}>{busy ? '…' : 'AutoSwitch → runtime'}</button>
      </div>
      <div className="kv">
        <b>Access</b><span>{e.entitlement.access}</span>
        <b>FREE остаток</b><span>{e.entitlement.freeRemaining ?? '— (source-backed не известно)'}</span>
        <b>Credits</b><span>{e.entitlement.creditsRemaining != null ? `${e.entitlement.creditsRemaining} ${e.entitlement.creditsCurrency ?? ''}` : '—'}</span>
        <b>След. дешёвый режим</b><span>{e.entitlement.nextCheaperMode ?? '—'}</span>
        <b>Источник</b><span>{e.entitlement.source}</span>
        <b>Решение (клиент)</b>
        <span style={{ color: d.ok ? 'var(--emerald)' : 'var(--rose)', fontWeight: 600 }}>
          {d.ok ? 'ALLOW' : 'DENY'} — {d.reason}
        </span>
        {apiDecision && (
          <>
            <b>Решение (runtime readback)</b>
            <span style={{ color: apiDecision.includes('DENY') || apiDecision.includes('исчерпан') || apiDecision.includes('не принадлежит') ? 'var(--rose)' : 'var(--emerald)', fontWeight: 600 }}>
              {apiDecision}{apiRunId ? ` · run_id=${apiRunId}` : ''}
            </span>
          </>
        )}
      </div>
      <div className="rnote">Source-backed режимы: {SOURCE_BACKED_MODES.map((m) => m.id).join(' / ')}. Off-peak скидки не выдумываются.</div>
    </div>
  );
}

function DealPanel() {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 10px', fontFamily: 'var(--head)', fontSize: 14 }}>Deal / Connection Radar</h3>
      <div className="rnote">Официальный registry: {OFFICIAL_REGISTRY.join(' · ')}. Только точный официальный источник = VERIFIED.</div>
      <div className="wrap2">
        {dealRadar().map((d) => (
          <div className="scard" key={d.id}>
            <div className="cat">{d.provider} · {d.kind}</div>
            <div className="nm">
              {d.title}{' '}
              <span className={`badge ${d.status === 'VERIFIED' ? '' : ''}`} style={d.status === 'VERIFIED' ? undefined : { background: 'rgba(251,191,36,.14)', color: 'var(--amber)', borderColor: 'rgba(251,191,36,.3)' }}>
                {d.status}
              </span>
            </div>
            <div className="trig">{d.detail}</div>
            {d.appliesTo && <div className="trig">только: {d.appliesTo.join(', ')}</div>}
            {d.reason && <div className="trig" style={{ color: 'var(--amber)' }}>{d.reason}</div>}
            <div className="trig" style={{ wordBreak: 'break-all' }}>source: {d.source}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CatalogPage() {
  const [query, setQuery] = useState('');
  const [activeCaps, setActiveCaps] = useState<Set<CapabilityId>>(new Set());
  const [kinds, setKinds] = useState<Set<'model' | 'agent'>>(new Set());
  const [freeOnly, setFreeOnly] = useState<boolean | null>(null);

  const filter: CatalogFilter = useMemo(
    () => ({ kinds, caps: activeCaps, free: freeOnly, access: new Set() }),
    [kinds, activeCaps, freeOnly],
  );

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    const byQuery = (e: Entity) => !q || `${e.name} ${e.provider}`.toLowerCase().includes(q);
    return applyFilter(ALL_ENTITIES, filter).filter(byQuery);
  }, [query, filter]);

  const { primary, paidOwned } = useMemo(() => splitBlocks(filtered), [filtered]);
  const cov = useMemo(() => coverageStatus(ALL_ENTITIES), []);

  const toggleCaps = (c: CapabilityId) => {
    const next = new Set(activeCaps);
    if (next.has(c)) next.delete(c);
    else next.add(c);
    setActiveCaps(next);
  };
  const toggleKind = (k: 'model' | 'agent') => {
    const next = new Set(kinds);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    setKinds(next);
  };
  const cycleFree = () => setFreeOnly(freeOnly === null ? true : freeOnly === true ? false : null);

  return (
    <div>
      <div className="pagehead">
        <h1>Catalog — ALL</h1>
        <p>
          Все сущности ({cov.total}: {cov.models} моделей + {cov.agents} агентов; {cov.free} FREE, {cov.paidOwned} PAID·OWNED).
          Фильтры = AND. Область: {cov.scope}.
        </p>
      </div>

      <EntitlementPanel />
      <DealPanel />

      <div className="toolbar">
        <div className="search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
          <input placeholder="Поиск по имени/провайдеру…" aria-label="Поиск сущностей" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </div>

      <div className="chips">
        <button className={`chip ${kinds.has('model') ? 'on' : ''}`} aria-pressed={kinds.has('model')} onClick={() => toggleKind('model')}>модели</button>
        <button className={`chip ${kinds.has('agent') ? 'on' : ''}`} aria-pressed={kinds.has('agent')} onClick={() => toggleKind('agent')}>агенты</button>
        <button className={`chip ${freeOnly === true ? 'on' : freeOnly === false ? 'on' : ''}`} aria-pressed={freeOnly !== null} onClick={cycleFree} style={freeOnly === false ? { borderColor: 'var(--rose)', color: 'var(--rose)' } : undefined}>
          {freeOnly === null ? 'free: любой' : freeOnly ? 'FREE' : 'paid'}
        </button>
        {(Object.keys(CAPS) as CapabilityId[]).map((id) => (
          <button key={id} className={`chip ${activeCaps.has(id) ? 'on' : ''}`} aria-pressed={activeCaps.has(id)} onClick={() => toggleCaps(id)}>
            {CAPS[id].icon}{CAPS[id].label}
          </button>
        ))}
      </div>
      <div className="rnote" style={{ marginTop: 8 }}>
        Выбрано (AND): {[...kinds].map((k) => `тип=${k}`).concat([...activeCaps].map((c) => `cap=${c}`)).concat(freeOnly !== null ? [`free=${freeOnly}`] : []).join(' + ') || 'нет фильтров'}
      </div>

      {primary.length > 0 && (
        <>
          <h3 style={{ fontFamily: 'var(--head)', marginTop: 18 }}>Primary ({primary.length})</h3>
          <div className="grid">
            {primary.map((e) => <EntityCard key={e.id} e={e} />)}
          </div>
        </>
      )}

      {paidOwned.length > 0 && (
        <>
          <h3 style={{ fontFamily: 'var(--head)', marginTop: 18 }}>PAID · OWNED ({paidOwned.length})</h3>
          <div className="grid">
            {paidOwned.map((e) => <EntityCard key={e.id} e={e} />)}
          </div>
        </>
      )}

      {filtered.length === 0 && <div className="empty">Ничего не найдено — измените фильтр или запрос.</div>}
    </div>
  );
}
