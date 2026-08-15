export interface Task {
  c: 'back' | 'in' | 'done';
  t: string;
  d: string;
}

export const TASKS: Task[] = [
  { c: 'done', t: 'Связь GPT↔MIMO (E2E)', d: 'ntfy → portable-os/MIMO/responses' },
  { c: 'done', t: 'App-shell каркас', d: '9 модулей, icon-first UI, hash-роутер' },
  { c: 'done', t: 'Каталог 400 моделей', d: 'models.seed.json + schema + генератор' },
  { c: 'done', t: 'capability-icons.svg', d: 'спрайт 10 способностей' },
  { c: 'in', t: 'router.py', d: '8-осевой routing (запушен)' },
  { c: 'in', t: 'Наполнение модулей', d: 'Skills/Agents/Workflow/Playground/MIMO/Observatory/Task Board' },
  { c: 'back', t: 'Извлечение скиллов', d: 'в .mimocode/skills/ из задач' },
  { c: 'back', t: 'Playground live API', d: 'подключить реальный провайдер' },
  { c: 'back', t: 'Observatory лайв-метрики', d: 'подключить orchestra_status.py' },
  { c: 'back', t: 'Agents Studio CRUD', d: 'сохранение агентов' },
];
