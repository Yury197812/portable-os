'use client';

import { useState } from 'react';
import { MODELS, type Model } from '@/lib/models';

const AXES = [
  { id: 'quality', label: 'Quality' },
  { id: 'latency', label: 'Latency (ниже лучше)' },
  { id: 'cost', label: 'Cost (ниже лучше)' },
  { id: 'context', label: 'Context' },
  { id: 'privacy', label: 'Privacy' },
  { id: 'availability', label: 'Availability' },
  { id: 'tool', label: 'tool_use' },
  { id: 'free', label: 'FREE' },
] as const;

const DEFAULTS: Record<string, number> = { quality: 5, latency: 5, cost: 4, context: 3, privacy: 3, availability: 3, tool: 5, free: 2 };

function score(m: Model, w: Record<string, number>): number {
  const norm = (v: number, max: number, inv: boolean) => {
    const x = Math.min(1, Math.max(0, v / max));
    return inv ? 1 - x : x;
  };
  return (
    w.quality * (m.q / 10) +
    w.latency * norm(m.lat, 2500, true) +
    w.cost * (m.free ? 1 : norm(m.cost, 15, true)) +
    w.context * norm(m.ctx || 0, 2000, false) +
    w.privacy * ((m.priv || 5) / 10) +
    w.availability * ((m.avail || 9) / 10) +
    w.tool * (m.tool ? 1 : 0) +
    w.free * (m.free ? 1 : 0)
  );
}

export default function RoutingPage() {
  const [w, setW] = useState<Record<string, number>>({ ...DEFAULTS });
  const ranked = [...MODELS]
    .map((m) => ({ m, sc: score(m, w) }))
    .sort((a, b) => b.sc - a.sc)
    .slice(0, 5);

  return (
    <div>
      <div className="pagehead">
        <h1>Routing Lab</h1>
        <p>Динамический выбор модели по 8 осям: quality / latency / cost / context / privacy / availability / tool_use / free.</p>
      </div>
      <div className="rl">
        <div className="card">
          <h3>Веса осей</h3>
          {AXES.map((a) => (
            <div className="slider" key={a.id}>
              <label>{a.label}</label>
              <input
                type="range"
                min={0}
                max={10}
                value={w[a.id]}
                aria-label={a.label}
                onChange={(e) => setW({ ...w, [a.id]: Number(e.target.value) })}
              />
              <span className="w">{w[a.id]}</span>
            </div>
          ))}
        </div>
        <div className="card">
          <h3>Топ-5 по текущим весам</h3>
          <div className="rank">
            {ranked.map((r, i) => (
              <div className="rankrow" key={r.m.id}>
                <span className="pos">{i + 1}</span>
                <span className="nm">{r.m.name}</span>
                <span className="sc">{r.sc.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
