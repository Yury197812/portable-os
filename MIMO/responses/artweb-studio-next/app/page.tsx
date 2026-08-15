'use client';

import { useMemo, useState } from 'react';
import { MODELS } from '@/lib/models';
import { CAPS, type CapabilityId } from '@/lib/capabilities';
import ModelCard from '@/components/ModelCard';

export default function CatalogPage() {
  const [query, setQuery] = useState('');
  const [activeCaps, setActiveCaps] = useState<Set<string>>(new Set());

  const filtered = useMemo(
    () =>
      MODELS.filter((m) => {
        const q = `${m.name} ${m.provider}`.toLowerCase();
        const okQ = !query || q.includes(query.toLowerCase());
        const okC = activeCaps.size === 0 || m.caps.some((c) => activeCaps.has(c));
        return okQ && okC;
      }),
    [query, activeCaps],
  );

  const toggle = (c: string) => {
    const next = new Set(activeCaps);
    if (c === '') next.clear();
    else if (next.has(c)) next.delete(c);
    else next.add(c);
    setActiveCaps(next);
  };

  return (
    <div>
      <div className="pagehead">
        <h1>Model Compare</h1>
        <p>Каталог моделей с icon-first возможностями и динамическим routing. FREE — подмножество, tool_use — first-class.</p>
      </div>

      <div className="toolbar">
        <div className="search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
          <input
            placeholder="Поиск по имени/провайдеру…"
            aria-label="Поиск моделей"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="chips">
        <button className={`chip ${activeCaps.size === 0 ? 'on' : ''}`} aria-pressed={activeCaps.size === 0} onClick={() => toggle('')}>
          Все
        </button>
        {(Object.keys(CAPS) as CapabilityId[]).map((id) => (
          <button key={id} className={`chip ${activeCaps.has(id) ? 'on' : ''}`} aria-pressed={activeCaps.has(id)} onClick={() => toggle(id)}>
            {CAPS[id].icon}
            {CAPS[id].label}
          </button>
        ))}
      </div>

      <div className="grid">
        {filtered.length ? (
          filtered.map((m) => <ModelCard key={m.id} m={m} />)
        ) : (
          <div className="empty">Ничего не найдено — измените фильтр или запрос.</div>
        )}
      </div>
    </div>
  );
}
