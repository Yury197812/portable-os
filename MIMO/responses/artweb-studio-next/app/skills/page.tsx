import { SKILLS } from '@/lib/skills';

export default function SkillsPage() {
  return (
    <div>
      <div className="pagehead">
        <h1>Skills Registry</h1>
        <p>Реестр переиспользуемых скиллов (извлечённых из задач).</p>
      </div>
      <div className="wrap2">
        {SKILLS.map((s) => (
          <div className="scard" key={s.n}>
            <span className="cat">{s.cat}</span>
            <div className="nm">{s.n}</div>
            {s.desc && <div className="trig">{s.desc}</div>}
            <div>{s.t.map((t) => <span className="tag" key={t}>{t}</span>)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
