import type { ReactNode } from 'react';

export type CapabilityId =
  | 'tool_use' | 'free' | 'reasoning' | 'vision' | 'audio'
  | 'web' | 'code' | 'memory' | 'safety' | 'speed';

interface CapDef {
  label: string;
  color: string;
  icon: ReactNode;
}

const svg = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    {d}
  </svg>
);

export const CAPS: Record<CapabilityId, CapDef> = {
  tool_use: { label: 'tool_use', color: '#8b5cf6', icon: svg(<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />) },
  free: { label: 'free', color: '#34d399', icon: svg(<><rect x="3" y="8" width="18" height="4" rx="1" /><path d="M12 8v13M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8M16.5 8a2.5 2.5 0 0 0 0-5C13 3 12 8 12 8" /></>) },
  reasoning: { label: 'reasoning', color: '#fbbf24', icon: svg(<><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" /><path d="M5 15l.6 1.4L7 17l-1.4.6L5 19l-.6-1.4L3 17l1.4-.6z" /></>) },
  vision: { label: 'vision', color: '#22d3ee', icon: svg(<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></>) },
  audio: { label: 'audio', color: '#f472b6', icon: svg(<path d="M3 10v4M7 6v12M11 3v18M15 6v12M19 10v4" />) },
  web: { label: 'web', color: '#38bdf8', icon: svg(<><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20" /></>) },
  code: { label: 'code', color: '#a3e635', icon: svg(<path d="M16 18l6-6-6-6M8 6l-6 6 6 6" />) },
  memory: { label: 'memory', color: '#2dd4bf', icon: svg(<><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" /></>) },
  safety: { label: 'safety', color: '#fb7185', icon: svg(<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />) },
  speed: { label: 'speed', color: '#fb923c', icon: svg(<path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />) },
};

export function CapabilityChip({ id }: { id: CapabilityId }) {
  const c = CAPS[id];
  if (!c) return null;
  return (
    <span className="cap" style={{ color: c.color, borderColor: `${c.color}44`, background: `${c.color}18` }}>
      {c.icon}
      {c.label}
    </span>
  );
}
