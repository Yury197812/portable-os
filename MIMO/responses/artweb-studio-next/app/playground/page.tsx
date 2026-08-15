'use client';

import { useEffect, useState } from 'react';

interface PlayModel {
  provider: string;
  id: string;
  name: string;
}

const PROXY = 'http://127.0.0.1:8890';

export default function PlaygroundPage() {
  const [models, setModels] = useState<PlayModel[]>([]);
  const [sel, setSel] = useState('ollama|qwen2.5:14b');
  const [temp, setTemp] = useState('0.7');
  const [prompt, setPrompt] = useState('Расскажи в двух предложениях, что такое ArtWeb Studio.');
  const [out, setOut] = useState('Загрузка моделей…');

  useEffect(() => {
    fetch(`${PROXY}/api/models`)
      .then((r) => r.json())
      .then((l: PlayModel[]) => setModels(l))
      .catch(() => setModels([]));
  }, []);

  const run = async () => {
    const [provider, model] = sel.split('|');
    setOut(`… запрос к ${model} …`);
    try {
      const r = await fetch(`${PROXY}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model, messages: [{ role: 'user', content: prompt }], temperature: parseFloat(temp) }),
      });
      const j = await r.json();
      setOut(j.error ? `Ошибка: ${j.error}` : `[${j.provider} · ${j.model} · ${j.latency_ms}ms]\n\n${j.content}`);
    } catch (e) {
      setOut(`Ошибка соединения с прокси (запусти playground_proxy.py на :8890): ${e}`);
    }
  };

  return (
    <div>
      <div className="pagehead">
        <h1>Playground</h1>
        <p>Живые вызовы моделей через локальный прокси (Ollama / OpenRouter).</p>
      </div>
      <div className="pg">
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} aria-label="Промпт для модели" />
        <div className="controls">
          <select value={sel} onChange={(e) => setSel(e.target.value)} aria-label="Модель">
            {models.length
              ? models.map((m) => <option key={m.id} value={`${m.provider}|${m.id}`}>{m.name}</option>)
              : <option value="ollama|qwen2.5:14b">Qwen2.5 14B · Ollama</option>}
          </select>
          <select value={temp} onChange={(e) => setTemp(e.target.value)} aria-label="Температура">
            <option>0.2</option>
            <option>0.7</option>
            <option>1.0</option>
          </select>
          <button className="btn" onClick={run}>▶ Run</button>
        </div>
        <div className="out" aria-live="polite">{out}</div>
      </div>
    </div>
  );
}
