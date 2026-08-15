import type { ReactNode } from 'react';

export interface Module {
  id: string;
  name: string;
  icon: ReactNode;
  desc: string;
}

const svg = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    {d}
  </svg>
);

export const MODULES: Module[] = [
  { id: 'catalog', name: 'Model Compare', icon: svg(<><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></>), desc: 'Каталог моделей: FREE-подмножество, tool_use first-class, без лимита 29.' },
  { id: 'routing', name: 'Routing Lab', icon: svg(<><circle cx="6" cy="19" r="3" /><circle cx="18" cy="5" r="3" /><path d="M6 16v-3a3 3 0 0 1 3-3h9" /></>), desc: 'Динамический выбор модели по 8 осям.' },
  { id: 'skills', name: 'Skills Registry', icon: svg(<><path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" /></>), desc: 'Реестр переиспользуемых скиллов.' },
  { id: 'agents', name: 'Agents Studio', icon: svg(<><rect x="3" y="7" width="15" height="12" rx="2" /><path d="M10 3h7a2 2 0 0 1 2 2v2" /><circle cx="8" cy="13" r="1" /><circle cx="13" cy="13" r="1" /></>), desc: 'Сборка агентов поверх моделей и скиллов.' },
  { id: 'workflow', name: 'Workflow Builder', icon: svg(<><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="12" r="3" /><path d="M6 9v6M9 12h6" /></>), desc: 'Визуальный конструктор цепочек шагов.' },
  { id: 'playground', name: 'Playground', icon: svg(<><path d="M6 9l6-5 6 5v10l-6 5-6-5V9z" /><path d="M12 22V9" /></>), desc: 'Песочница для живых вызовов моделей.' },
  { id: 'mimo', name: 'MIMO Sync', icon: svg(<><path d="M21 12a9 9 0 1 1-2.6-6.4" /><path d="M21 3v6h-6" /></>), desc: 'Двусторонняя связь MIMO↔GPT.' },
  { id: 'observatory', name: 'Observatory', icon: svg(<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></>), desc: 'Метрики, логи, дрифт дашборда.' },
  { id: 'taskboard', name: 'Task Board', icon: svg(<><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18M15 3v18M3 9h6M3 15h6M15 9h6M15 15h6" /></>), desc: 'Очередь задач оркестра.' },
  { id: 'compare', name: 'Сравнить', icon: svg(<><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3" /></>), desc: 'Побочное сравнение двух моделей и отзывы.' },
  { id: 'about', name: 'О проекте', icon: svg(<><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></>), desc: 'Описание проекта и контакты.' },
];

export function moduleName(id: string): string {
  return MODULES.find((m) => m.id === id)?.name ?? 'Studio';
}
