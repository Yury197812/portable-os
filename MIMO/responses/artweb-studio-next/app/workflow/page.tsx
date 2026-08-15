'use client';

import { useState } from 'react';

export default function WorkflowPage() {
  const [steps, setSteps] = useState(['Ingest', 'Clean', 'Analyze', 'Report']);
  const [input, setInput] = useState('');

  const add = () => {
    if (!input.trim()) return;
    setSteps([...steps, input.trim()]);
    setInput('');
  };
  const rm = (i: number) => setSteps(steps.filter((_, j) => j !== i));

  return (
    <div>
      <div className="pagehead">
        <h1>Workflow Builder</h1>
        <p>Визуальный конструктор цепочек шагов.</p>
      </div>
      <div className="wf">
        {steps.map((s, i) => (
          <div key={i}>
            <div className="wfnode">
              <div className="box"><span className="idx">{String(i + 1).padStart(2, '0')}</span>{s}</div>
              <button className="x" aria-label="Удалить шаг" onClick={() => rm(i)}>×</button>
            </div>
            {i < steps.length - 1 && <div className="wfline" />}
          </div>
        ))}
      </div>
      <div className="wfadd">
        <input placeholder="Название шага…" aria-label="Название шага" value={input} onChange={(e) => setInput(e.target.value)} />
        <button className="btn" onClick={add}>+ Шаг</button>
      </div>
    </div>
  );
}
