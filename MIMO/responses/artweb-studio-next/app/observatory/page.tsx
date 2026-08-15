'use client';

import { useEffect, useState } from 'react';

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Track { [k: string]: any }

export default function ObservatoryPage() {
  const [snap, setSnap] = useState<any>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    fetch('http://127.0.0.1:8890/api/orchestra')
      .then((r) => r.json())
      .then((d) => (d.error ? setErr(d.error) : setSnap(d)))
      .catch((e) => setErr(String(e)));
  }, []);

  const tracks: Record<string, Track> = snap?.tracks ?? {};
  const drift = snap?.drift_check?.drift_minutes_per_track ?? {};

  return (
    <div>
      <div className="pagehead">
        <h1>Observatory</h1>
        <p>Реальные метрики оркестра (truthful snapshot :8091 через прокси).</p>
      </div>
      {err && <div className="placehold"><h3>Дашборд недоступен</h3><p>{err}</p></div>}
      {!snap && !err && <div className="placehold"><h3>Загрузка метрик…</h3></div>}
      {snap && (
        <div aria-live="polite">
          <div className="statgrid">
            <div className="stat"><div className="v">{snap.results_for_gpt?.length ?? 0}</div><div className="l">RESULT для GPT</div></div>
            <div className="stat"><div className="v">{tracks.T3_registry?.total_workers ?? 0}</div><div className="l">воркеров</div></div>
            <div className="stat"><div className="v">{tracks.T2_inventory?.total_capabilities ?? 0}</div><div className="l">capabilities</div></div>
            <div className="stat"><div className="v">{(tracks.T4_atom_graph?.atoms ?? 0)}+{tracks.T4_atom_graph?.quarks ?? 0}</div><div className="l">атомы + кварки</div></div>
            <div className="stat"><div className="v">{(tracks.T5_lean_chain?.claims_proved ?? 0)}/{(tracks.T5_lean_chain?.claims_total ?? 0)}</div><div className="l">Lean доказано</div></div>
            <div className="stat"><div className="v">{tracks.T1_supervisor?.seen_count ?? 0}</div><div className="l">событий supervisor</div></div>
          </div>
          <h3 style={{ fontFamily: 'var(--head)' }}>Дрифт треков (мин, порог 120)</h3>
          <div className="chart">
            {Object.entries(tracks).map(([k]) => {
              const dr = drift[k];
              const drs = dr == null ? '—' : dr > 120 ? `${Math.round(dr)}м` : `${dr.toFixed(1)}м`;
              return (
                <div className="row" key={k}>
                  <span className="lb">{k}</span>
                  <div className="bar" style={{ width: Math.min(200, dr || 0), background: dr > 120 ? 'var(--rose)' : 'var(--accent)' }} />
                  <span style={{ color: dr > 120 ? 'var(--rose)' : 'var(--text2)' }}>{drs}</span>
                </div>
              );
            })}
          </div>
          <div className="kv" style={{ marginTop: 14 }}>
            <b>Вердикт</b>
            <span>{snap.drift_check?.verdict ?? '—'} · бакет {snap.drift_check?.bucket_minutes ?? '—'} мин · {String(snap.generated_at ?? '').slice(0, 19)}Z</span>
          </div>
        </div>
      )}
    </div>
  );
}
