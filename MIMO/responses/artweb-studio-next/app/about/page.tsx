import { MODULES } from '@/lib/modules';

const FEATURES = [
  ['Model Compare', 'Каталог ~400 моделей с icon-first возможностями: FREE — подмножество, tool_use — first-class.'],
  ['Routing Lab', 'Динамический выбор модели по 8 осям: quality / latency / cost / context / privacy / availability / tool_use / free.'],
  ['Playground', 'Живые вызовы моделей через локальный прокси — Ollama qwen2.5:14b и OpenRouter free.'],
  ['Observatory', 'Реальные метрики оркестра: воркеры, capabilities, дрифт треков, вердикт правдивости.'],
  ['Skills Registry', 'Реестр переиспользуемых скиллов, извлечённых из задач.'],
  ['Agents Studio', 'Сборка агентов поверх моделей и скиллов.'],
  ['Workflow Builder', 'Визуальный конструктор цепочек шагов.'],
  ['MIMO Sync', 'Двусторонняя связь MIMO↔GPT: ntfy → portable-os/MIMO/responses.'],
  ['Task Board', 'Очередь задач оркестра (канбан).'],
];

const CONTACTS = [
  ['GitHub', 'https://github.com/Yury197812/portable-os', 'репозиторий, MIMO/responses — обратный канал MIMO→GPT'],
  ['Email', 'apohob5@gmail.com', 'владелец проекта'],
  ['Канал MIMO↔GPT', 'ntfy: artweb-mimo-bus-20260814-8d3f2a761c4e', 'wakeup-канал для задач от GPT'],
];

export default function AboutPage() {
  return (
    <div>
      <div className="pagehead">
        <h1>О проекте</h1>
        <p>ArtWeb Studio — командный центр конструктора сайтов и оркестра моделей.</p>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <p style={{ margin: 0, color: 'var(--text2)', fontSize: 14 }}>
          ArtWeb Studio — это единая точка управления каталогом моделей, динамическим routing&apos;ом,
          скиллами, агентами и задачами. Тёмный премиум-интерфейс, icon-first язык способностей
          (tool_use / free / reasoning / vision / audio / web / code / memory / safety / speed) и живое
          подключение к локальным и облачным моделям через прокси. Собрано на Next.js 14 (App Router) + TypeScript.
        </p>
      </div>

      <h3 style={{ fontFamily: 'var(--head)' }}>Что внутри ({MODULES.length - 1} модулей)</h3>
      <div className="wrap2" style={{ marginBottom: 16 }}>
        {FEATURES.map(([t, d]) => (
          <div className="scard" key={t}>
            <span className="cat">модуль</span>
            <div className="nm">{t}</div>
            <div className="trig">{d}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Контакты</h3>
        {CONTACTS.map(([k, v, d]) => (
          <div className="kv" key={k}>
            <b>{k}</b>
            <span>
              <span className="mono">{v}</span>
              <div style={{ color: 'var(--text3)', fontSize: 11.5 }}>{d}</div>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
