'use client';

import { usePathname } from 'next/navigation';
import { moduleName } from '@/lib/modules';

export default function Topbar() {
  const pathname = usePathname();
  const seg = pathname === '/' ? 'catalog' : pathname.split('/')[1];
  const name = moduleName(seg);

  return (
    <header className="topbar">
      <div className="logo">
        <span className="mark">A</span>
        ArtWeb Studio
      </div>
      <div className="crumbs">
        <span>Studio</span>
        <span className="sep">/</span>
        <b>{name}</b>
      </div>
      <div className="cmd">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
        <input placeholder="Command center — модель, модуль, capability…" aria-label="Командный центр — поиск моделей и модулей" />
      </div>
      <div className="statuspill">
        <span className="dot" />
        MIMO Sync · Live
      </div>
    </header>
  );
}
