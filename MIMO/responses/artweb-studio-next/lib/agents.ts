import type { CapabilityId } from './capabilities';

export interface Agent {
  n: string;
  r: string;
  model: string;
  skills: string;
  caps: CapabilityId[];
}

export const AGENTS: Agent[] = [
  { n: 'Web Designer', r: 'дизайн сайтов', model: 'GPT-4o mini', skills: 'frontend-design, product-design, imagegen', caps: ['vision', 'tool_use'] },
  { n: 'Data Analyst', r: 'аналитика', model: 'DeepSeek-V3', skills: 'data-analytics, xlsx-official', caps: ['code', 'tool_use'] },
  { n: 'Code Reviewer', r: 'ревью кода', model: 'Claude 3.5 Haiku', skills: 'lean-verify', caps: ['code', 'tool_use', 'safety'] },
  { n: 'Researcher', r: 'исследования', model: 'GPT-4o mini', skills: 'arxiv, deep-research, super-research', caps: ['web', 'reasoning', 'tool_use'] },
  { n: 'UI Tester', r: 'автотесты UI', model: 'Gemini 1.5 Flash', skills: 'ui-operator, ui-chain, playwright', caps: ['vision', 'tool_use'] },
  { n: 'Doc Writer', r: 'документы', model: 'Claude 3.5 Opus', skills: 'docx-official, pptx-official', caps: ['tool_use', 'reasoning'] },
];
