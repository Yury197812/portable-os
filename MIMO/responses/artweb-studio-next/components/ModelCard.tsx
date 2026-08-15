import type { Model } from '@/lib/models';
import { CapabilityChip } from '@/lib/capabilities';

export default function ModelCard({ m }: { m: Model }) {
  return (
    <div className="mcard">
      <div className="top">
        <div>
          <div className="name">{m.name}</div>
          <div className="provider">{m.provider} · {m.mod}</div>
        </div>
        {m.free && <span className="badge">FREE</span>}
      </div>
      <div className="caps">
        {m.caps.map((c) => <CapabilityChip key={c} id={c} />)}
      </div>
      <div className="meta">
        <span><b>Q</b> {m.q}/10</span>
        <span><b>Lat</b> {m.lat}ms</span>
        <span><b>Cost</b> {m.cost ? `$${m.cost}` : '0'}</span>
        <span><b>Ctx</b> {m.ctx ? `${m.ctx}K` : '—'}</span>
      </div>
    </div>
  );
}
