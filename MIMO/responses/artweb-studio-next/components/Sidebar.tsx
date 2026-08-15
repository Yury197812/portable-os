'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MODULES } from '@/lib/modules';
import { MODELS } from '@/lib/models';

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="sidebar" aria-label="Основная навигация">
      <div className="side-sec">Модули</div>
      {MODULES.map((m) => {
        const href = m.id === 'catalog' ? '/' : `/${m.id}`;
        const active = m.id === 'catalog' ? pathname === '/' : pathname.startsWith(href);
        return (
          <Link
            key={m.id}
            href={href}
            className={`navitem ${active ? 'active' : ''}`}
            aria-current={active ? 'page' : undefined}
            aria-label={m.name}
          >
            {m.icon}
            <span>{m.name}</span>
            {m.id === 'catalog' && <span className="count">{MODELS.length}</span>}
          </Link>
        );
      })}
    </nav>
  );
}
