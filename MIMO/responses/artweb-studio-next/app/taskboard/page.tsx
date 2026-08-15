import { TASKS } from '@/lib/tasks';

const LABEL: Record<string, string> = { back: 'BACKLOG', in: 'IN PROGRESS', done: 'DONE' };
const TITLE: Record<string, string> = { back: 'Backlog', in: 'In Progress', done: 'Done' };

export default function TaskBoardPage() {
  return (
    <div>
      <div className="pagehead">
        <h1>Task Board</h1>
        <p>Очередь задач оркестра и их статусы.</p>
      </div>
      <div className="kanban">
        {(['back', 'in', 'done'] as const).map((c) => (
          <div className="kcol" key={c}>
            <h3>{TITLE[c]}</h3>
            {TASKS.filter((t) => t.c === c).map((t, i) => (
              <div className="task" key={`${t.t}-${i}`}>
                <div className="t">{t.t}</div>
                <div className="d">{t.d}</div>
                <div className="p">{LABEL[c]}</div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
