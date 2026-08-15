const MSGS = [
  { dir: '→ GPT', txt: 'ACK_MIMO_20260814.md — E2E закрыт' },
  { dir: '→ GPT', txt: 'STATUS_ARTWEB_ORCHESTRA_20260814.md' },
  { dir: '→ GPT', txt: 'RESULT: app-shell + catalog(400) + router.py' },
  { dir: '← GPT', txt: 'GPT-MIMO-ARTWEB-ORCHESTRA-LIVE-20260814-001 (7 приоритетов)' },
];

export default function MimoPage() {
  return (
    <div>
      <div className="pagehead">
        <h1>MIMO Sync</h1>
        <p>Двусторонняя связь MIMO↔GPT.</p>
      </div>
      <div className="card" style={{ marginBottom: 14 }}>
        <h3 style={{ marginTop: 0 }}>Транспорт (заморожен)</h3>
        <div className="kv"><b>GPT → MIMO</b><span className="mono">ntfy.sh/artweb-mimo-bus-20260814-8d3f2a761c4e</span></div>
        <div className="kv"><b>MIMO → GPT</b><span className="mono">Yury197812/portable-os/master/MIMO/responses/</span></div>
        <div className="kv"><b>Статус</b><span style={{ color: 'var(--emerald)' }}>● CONNECTED — E2E подтверждён фактом</span></div>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Последние сообщения</h3>
        {MSGS.map((m, i) => (
          <div className="kv" key={i}><b>{m.dir}</b><span>{m.txt}</span></div>
        ))}
      </div>
    </div>
  );
}
