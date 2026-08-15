'use client';

import { useEffect, useState } from 'react';
import { AGENTS as SEED, type Agent } from '@/lib/agents';
import { CapabilityChip } from '@/lib/capabilities';

export default function AgentsPage() {
  const [list, setList] = useState<Agent[]>(SEED);
  const [name, setName] = useState('');
  const [role, setRole] = useState('');

  useEffect(() => {
    try {
      const v = JSON.parse(localStorage.getItem('artweb_agents') || 'null');
      if (Array.isArray(v) && v.length) setList(v);
    } catch {}
  }, []);

  const persist = (l: Agent[]) => {
    setList(l);
    try { localStorage.setItem('artweb_agents', JSON.stringify(l)); } catch {}
  };
  const add = () => {
    if (!name.trim()) return;
    persist([...list, { n: name.trim(), r: role.trim() || 'агент', model: 'Qwen2.5 14B · Ollama', skills: '', caps: ['tool_use'] }]);
    setName(''); setRole('');
  };
  const rm = (i: number) => persist(list.filter((_, j) => j !== i));

  return (
    <div>
      <div className="pagehead">
        <h1>Agents Studio</h1>
        <p>Сборка и настройка агентов поверх моделей и скиллов.</p>
      </div>
      <div className="wrap2">
        {list.map((a, i) => (
          <div className="acard" key={`${a.n}-${i}`}>
            <span className="role">{a.r}</span>
            <div className="nm" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              {a.n}
              <button className="x" aria-label="Удалить агента" onClick={() => rm(i)}>×</button>
            </div>
            <div className="meta">модель: <b>{a.model}</b></div>
            <div>{a.skills.split(', ').filter(Boolean).map((s) => <span className="tag" key={s}>{s}</span>)}</div>
            <div className="caps">{a.caps.map((c) => <CapabilityChip key={c} id={c} />)}</div>
          </div>
        ))}
      </div>
      <div className="card" style={{ marginTop: 14 }}>
        <h3 style={{ marginTop: 0 }}>Добавить агента</h3>
        <div className="wfadd">
          <input placeholder="Имя" aria-label="Имя агента" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="Роль" aria-label="Роль агента" value={role} onChange={(e) => setRole(e.target.value)} />
          <button className="btn" onClick={add}>+ Агент</button>
        </div>
      </div>
    </div>
  );
}
