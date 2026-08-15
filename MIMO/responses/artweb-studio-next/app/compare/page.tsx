'use client';

import { useEffect, useState } from 'react';
import { MODELS, type Model } from '@/lib/models';
import { CapabilityChip } from '@/lib/capabilities';

interface ORPricing { prompt?: string; completion?: string; input_cache_read?: string; }
interface ORProvider { context_length?: number; max_completion_tokens?: number; is_moderated?: boolean; }
interface ORModel {
  id: string;
  name?: string;
  description?: string;
  context_length?: number;
  pricing?: ORPricing;
  top_provider?: ORProvider;
  knowledge_cutoff?: string | null;
}
interface Review {
  id: number;
  model: string;
  author: string;
  rating: number;
  text: string;
  ts: string;
}

const PROXY = 'http://127.0.0.1:8890';

const FIELDS: { label: string; fmt: (m: Model) => string }[] = [
  { label: 'Провайдер', fmt: (m) => m.provider },
  { label: 'Модальность', fmt: (m) => m.mod },
  { label: 'Качество', fmt: (m) => `${m.q}/10` },
  { label: 'Латентность', fmt: (m) => `${m.lat}ms` },
  { label: 'Цена', fmt: (m) => (m.free ? 'FREE' : `$${m.cost}/1M`) },
  { label: 'Контекст', fmt: (m) => (m.ctx ? `${m.ctx}K` : '—') },
  { label: 'Приватность', fmt: (m) => `${m.priv}/10` },
  { label: 'Доступность', fmt: (m) => `${m.avail}/10` },
];

function perM(v?: string): string {
  if (!v) return '—';
  return `$${(parseFloat(v) * 1e6).toFixed(2)}/1M`;
}

function findOR(orList: ORModel[], name: string): ORModel | null {
  const tokens = name.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length >= 2);
  let best: ORModel | null = null;
  let bestScore = 0;
  for (const m of orList) {
    const hay = `${m.id} ${m.name || ''}`.toLowerCase();
    let s = 0;
    for (const t of tokens) if (hay.includes(t)) s++;
    if (s > bestScore) { bestScore = s; best = m; }
  }
  return bestScore >= Math.min(2, tokens.length) ? best : null;
}

function ORCard({ name, or }: { name: string; or: ORModel | null }) {
  return (
    <div className="card">
      <h3>{name} — данные OpenRouter</h3>
      <div className="rnote">Реальные данные из OpenRouter API (отзывов/рейтингов OpenRouter не отдаёт).</div>
      {or ? (
        <>
          <div className="kv"><b>Описание</b><span style={{ color: 'var(--text2)' }}>{or.description || '—'}</span></div>
          <div className="kv"><b>Цена</b><span className="mono">prompt {perM(or.pricing?.prompt)} · completion {perM(or.pricing?.completion)}</span></div>
          <div className="kv"><b>Контекст</b><span>{or.context_length ? `${or.context_length.toLocaleString()} токенов` : '—'}</span></div>
          <div className="kv"><b>Макс. токенов ответа</b><span>{or.top_provider?.max_completion_tokens?.toLocaleString() ?? '—'}</span></div>
          <div className="kv"><b>Knowledge cutoff</b><span>{or.knowledge_cutoff ?? '—'}</span></div>
        </>
      ) : (
        <div className="rnote">Не найдено соответствие в каталоге OpenRouter.</div>
      )}
    </div>
  );
}

function UserReviews({ modelId }: { modelId: string }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [author, setAuthor] = useState('');
  const [rating, setRating] = useState(0);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [myReviews, setMyReviews] = useState<Set<number>>(new Set());

  useEffect(() => {
    setReviews([]);
    fetch(`${PROXY}/api/reviews?model=${modelId}`)
      .then((r) => r.json())
      .then((d) => setReviews(d.reviews || []))
      .catch(() => {});
  }, [modelId]);

  useEffect(() => {
    try {
      const v = JSON.parse(localStorage.getItem('my_review_ids') || '[]');
      if (Array.isArray(v)) setMyReviews(new Set(v.map(Number)));
    } catch {}
  }, []);

  const submit = async () => {
    if (!text.trim()) { setErr('Напишите текст отзыва.'); return; }
    if (!rating) { setErr('Поставьте оценку (звёзды).'); return; }
    setBusy(true); setErr('');
    try {
      const r = await fetch(`${PROXY}/api/reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId, author, rating, text }),
      });
      const j = await r.json();
      if (r.ok) {
        setReviews([j, ...reviews]);
        const next = new Set(myReviews); next.add(j.id); setMyReviews(next);
        try { localStorage.setItem('my_review_ids', JSON.stringify([...next])); } catch {}
        setAuthor(''); setRating(0); setText('');
      } else {
        setErr(j.error || 'Ошибка сохранения.');
      }
    } catch (e) {
      setErr(`Ошибка соединения: ${e}`);
    } finally {
      setBusy(false);
    }
  };

  const del = async (id: number) => {
    try {
      const r = await fetch(`${PROXY}/api/reviews/${id}`, { method: 'DELETE' });
      if (r.ok) {
        setReviews(reviews.filter((x) => x.id !== id));
        const next = new Set(myReviews); next.delete(id); setMyReviews(next);
        try { localStorage.setItem('my_review_ids', JSON.stringify([...next])); } catch {}
      }
    } catch {}
  };

  return (
    <div className="card">
      <h3>Отзывы пользователей</h3>
      <div className="rnote">Оставляйте отзывы — они сохраняются в SQLite и видны всем.</div>

      {reviews.length ? (
        reviews.map((r) => (
          <div className="review" key={r.id}>
            <div className="rh">
              <b>{r.author}</b>
              <span className="stars" aria-label={`${r.rating} из 5`}>{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</span>
              <span className="rd">{r.ts}</span>
              {myReviews.has(r.id) && (
                <button className="x" aria-label="Удалить отзыв" onClick={() => del(r.id)}>×</button>
              )}
            </div>
            <div className="rt">{r.text}</div>
          </div>
        ))
      ) : (
        <div className="rnote">Отзывов пока нет — будьте первым.</div>
      )}

      <div className="rev-form">
        <div className="stars-input" role="radiogroup" aria-label="Оценка">
          {[1, 2, 3, 4, 5].map((n) => (
            <button key={n} type="button" className={`star-btn ${n <= rating ? 'on' : ''}`} aria-label={`${n} из 5`} aria-pressed={n <= rating} onClick={() => setRating(n)}>
              ★
            </button>
          ))}
        </div>
        <input className="rev-input" placeholder="Ваше имя (необязательно)" aria-label="Имя" value={author} onChange={(e) => setAuthor(e.target.value)} />
        <textarea className="rev-textarea" placeholder="Текст отзыва…" aria-label="Текст отзыва" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="rev-row">
          <button className="btn" onClick={submit} disabled={busy}>{busy ? 'Отправка…' : 'Отправить отзыв'}</button>
          {err && <span className="rev-err" role="alert">{err}</span>}
        </div>
      </div>
    </div>
  );
}

export default function ComparePage() {
  const [a, setA] = useState('gpt-4o-mini');
  const [b, setB] = useState('claude-haiku');
  const [orList, setOrList] = useState<ORModel[]>([]);

  useEffect(() => {
    fetch(`${PROXY}/api/openrouter`)
      .then((r) => r.json())
      .then((d) => { if (Array.isArray(d.data)) setOrList(d.data); })
      .catch(() => {});
  }, []);

  const ma = MODELS.find((m) => m.id === a) ?? MODELS[0];
  const mb = MODELS.find((m) => m.id === b) ?? MODELS[1];
  const ora = findOR(orList, ma.name);
  const orb = findOR(orList, mb.name);
  const opts = MODELS.map((m) => <option key={m.id} value={m.id}>{m.name}</option>);

  return (
    <div>
      <div className="pagehead">
        <h1>Сравнение моделей</h1>
        <p>Побочное сравнение двух моделей + реальные данные OpenRouter + отзывы пользователей.</p>
      </div>

      <div className="toolbar">
        <select className="cmp-select" value={a} onChange={(e) => setA(e.target.value)} aria-label="Модель A">{opts}</select>
        <span className="sep2">vs</span>
        <select className="cmp-select" value={b} onChange={(e) => setB(e.target.value)} aria-label="Модель B">{opts}</select>
      </div>

      <div className="reviews">
        <div className="rev-col">
          <ORCard name={ma.name} or={ora} />
          <UserReviews modelId={ma.id} />
        </div>
        <div className="rev-col">
          <ORCard name={mb.name} or={orb} />
          <UserReviews modelId={mb.id} />
        </div>
      </div>

      <table className="cmp">
        <thead>
          <tr><th>Параметр</th><th>{ma.name}</th><th>{mb.name}</th></tr>
        </thead>
        <tbody>
          {FIELDS.map((f) => (
            <tr key={f.label}>
              <td>{f.label}</td>
              <td>{f.fmt(ma)}</td>
              <td>{f.fmt(mb)}</td>
            </tr>
          ))}
          <tr>
            <td>Возможности</td>
            <td><div className="caps">{ma.caps.map((c) => <CapabilityChip key={c} id={c} />)}</div></td>
            <td><div className="caps">{mb.caps.map((c) => <CapabilityChip key={c} id={c} />)}</div></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
