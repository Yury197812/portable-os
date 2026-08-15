export interface Skill {
  n: string;
  cat: string;
  t: string[];
  desc?: string;
}

// Representative seed. The full 141-skill inventory lives in
// ../artweb-studio/skills.seed.json (extracted from WORKER-REGISTRY.json).
export const SKILLS: Skill[] = [
  { n: 'frontend-design', cat: 'дизайн', t: ['сайт', 'лендинг', 'UI'], desc: 'Отличительный визуальный дизайн интерфейсов.' },
  { n: 'product-design', cat: 'дизайн', t: ['продукт', 'UX', 'прототип'], desc: 'Продуктовый дизайн и UX-исследования.' },
  { n: 'design-blueprint', cat: 'дизайн', t: ['спека', 'DESIGN.md', 'макет'], desc: 'Структурированная спека перед сборкой.' },
  { n: 'imagegen', cat: 'дизайн', t: ['изображение', 'иллюстрация'], desc: 'Генерация растровых изображений.' },
  { n: 'data-analytics', cat: 'данные', t: ['метрики', 'KPI', 'дашборд'], desc: 'Количественный продуктовый анализ.' },
  { n: 'xlsx-official', cat: 'офис', t: ['xlsx', 'таблица', 'csv'], desc: 'Работа с электронными таблицами.' },
  { n: 'docx-official', cat: 'офис', t: ['docx', 'отчёт', 'word'], desc: 'Документы Word.' },
  { n: 'pptx-official', cat: 'офис', t: ['презентация', 'слайды'], desc: 'Презентации PowerPoint.' },
  { n: 'pdf-official', cat: 'офис', t: ['pdf', 'OCR', 'выписка'], desc: 'Генерация и разбор PDF.' },
  { n: 'arxiv', cat: 'research', t: ['arxiv', 'статья', 'цитата'], desc: 'Поиск и цитирование статей arXiv.' },
  { n: 'deep-research', cat: 'research', t: ['исследование', 'источники'], desc: 'Многоисточниковое исследование.' },
  { n: 'super-research', cat: 'research', t: ['эксперимент', 'абляция'], desc: 'Автономное исследование с доказательствами.' },
  { n: 'lean-verify', cat: 'инфра', t: ['lean', 'теорема', 'proof'], desc: 'Формальная верификация Lean 4.' },
  { n: 'genome-diff', cat: 'инфра', t: ['геном', 'хромосома'], desc: 'Сравнение компонентных геномов.' },
  { n: 'device-adapter', cat: 'инфра', t: ['adb', 'android'], desc: 'Адаптеры устройств (adb/scrcpy).' },
  { n: 'ui-operator', cat: 'инфра', t: ['браузер', 'click', 'shot'], desc: 'Браузерная автоматизация.' },
  { n: 'ui-chain', cat: 'инфра', t: ['многошаговый', 'flow'], desc: 'Многошаговые UI-цепочки.' },
  { n: 'dashboard-guard', cat: 'инфра', t: ['регрессия', 'снимок'], desc: 'Regression-guard дашборда.' },
  { n: 'now-iso', cat: 'инфра', t: ['время', 'ISO'], desc: 'Текущее UTC-время.' },
  { n: 'sha16', cat: 'инфра', t: ['хеш', 'sha256'], desc: 'Отпечаток файла.' },
  { n: 'mtime', cat: 'инфра', t: ['mtime', 'дата'], desc: 'Время изменения файла.' },
  { n: 'playwright', cat: 'инфра', t: ['браузер', 'автоматизация'], desc: 'Playwright-автоматизация.' },
  { n: 'skill-creator', cat: 'мета', t: ['новый скилл'], desc: 'Создание скиллов.' },
  { n: 'memory-search', cat: 'мета', t: ['траектория', 'SQL'], desc: 'Поиск по траекториям.' },
];
