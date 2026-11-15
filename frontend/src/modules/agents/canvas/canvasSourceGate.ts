export const CANVAS_SOURCE_LIMIT = 100_000;

export const CANVAS_EXPORTS = [
  'Stack',
  'Row',
  'Grid',
  'H1',
  'H2',
  'H3',
  'Text',
  'Divider',
  'Card',
  'CardHeader',
  'CardBody',
  'Stat',
  'Callout',
  'Pill',
  'Table',
  'BarChart',
  'LineChart',
  'PieChart',
  'useHostTheme',
  'useState',
  'useMemo',
  'useEffect',
] as const;

const ALLOWED = new Set<string>(CANVAS_EXPORTS);
const BLOCKED_CALL = /\b(fetch|XMLHttpRequest|WebSocket|eval|Function)\b|dangerouslySetInnerHTML|javascript\s*:|\bimport\s*\(/;
const NAMED_IMPORT = /^\s*import\s+(type\s+)?([\s\S]*?)\s+from\s+['"]([^'"]+)['"]\s*;?/gm;
const OTHER_IMPORT = /^\s*(?:import\s+['"][^'"]+['"]|export\s+[\s\S]*?\sfrom\s+['"][^'"]+['"])/gm;
const IDENTIFIER = /^[$A-Za-z_][$\w]*$/;

export function isCanvasFile(path: string): boolean {
  const normalized = path.replace(/\\/g, '/').replace(/^\/+/, '');
  if (!normalized.startsWith('.canvases/') || !normalized.endsWith('.canvas.tsx')) return false;
  const name = normalized.slice('.canvases/'.length);
  return name.length > '.canvas.tsx'.length && !name.includes('/') && !name.includes('..');
}

export function canvasTitle(path: string): string {
  const name = path.replace(/\\/g, '/').split('/').pop() || path;
  return name.replace(/\.canvas\.tsx$/, '');
}

export function canvasNameFromToken(token: string): string | null {
  const normalized = token.trim().replace(/\\/g, '/').replace(/^\/workspace\//, '').replace(/^\.\//, '');
  const file = normalized.match(/(?:^|\/)([a-z0-9]+(?:-[a-z0-9]+)*)\.canvas\.tsx$/i);
  if (file) return file[1];
  if (/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(normalized)) return normalized;
  return null;
}

export function canvasPathForName(paths: string[], name: string): string {
  const wanted = name.trim().toLowerCase();
  return paths.find((path) => canvasTitle(path).toLowerCase() === wanted) || '';
}

export function canvasNamesInText(text: string): string[] {
  const names = new Set<string>();
  const filePattern = /(?:\/workspace\/)?\.canvases\/([a-z0-9]+(?:-[a-z0-9]+)*)\.canvas\.tsx/gi;
  let match: RegExpExecArray | null;
  while ((match = filePattern.exec(text))) names.add(match[1]);
  if (/canvas/i.test(text)) {
    const codePattern = /`([a-z0-9]+(?:-[a-z0-9]+)*)`/g;
    while ((match = codePattern.exec(text))) names.add(match[1]);
    const wordPattern = /\bcanvas\s+([a-z0-9]+(?:-[a-z0-9]+)*)\b/gi;
    while ((match = wordPattern.exec(text))) {
      if (match[1].includes('-')) names.add(match[1]);
    }
  }
  return [...names];
}

export interface CanvasBinding {
  local: string;
  imported: string;
}

export function canvasBindings(source: string): CanvasBinding[] {
  const bindings: CanvasBinding[] = [];
  NAMED_IMPORT.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = NAMED_IMPORT.exec(source))) {
    if (match[1] || match[3] !== 'compassx/canvas') continue;
    const clause = match[2].trim();
    const open = clause.indexOf('{');
    const close = clause.lastIndexOf('}');
    if (open < 0 || close < open) continue;
    for (const part of clause.slice(open + 1, close).split(',')) {
      const piece = part.trim();
      if (!piece) continue;
      const [importedRaw, localRaw] = piece.split(/\s+as\s+/);
      const imported = (importedRaw || '').trim();
      const local = (localRaw || imported).trim();
      if (IDENTIFIER.test(imported) && IDENTIFIER.test(local)) {
        bindings.push({ imported, local });
      }
    }
  }
  return bindings;
}

export function checkCanvasSource(source: string): string | null {
  if (typeof source !== 'string' || !source.trim()) return 'This canvas is empty.';
  if (source.length > CANVAS_SOURCE_LIMIT) return 'This canvas is too large.';
  if (BLOCKED_CALL.test(source)) return 'This canvas uses a call that is not allowed.';
  OTHER_IMPORT.lastIndex = 0;
  if (OTHER_IMPORT.test(source)) return 'A canvas can only import from compassx/canvas.';

  NAMED_IMPORT.lastIndex = 0;
  let match: RegExpExecArray | null;
  let sawValueImport = false;
  while ((match = NAMED_IMPORT.exec(source))) {
    if (match[3] !== 'compassx/canvas') return 'A canvas can only import from compassx/canvas.';
    if (match[1]) continue;
    const clause = match[2].trim();
    if (!clause.includes('{')) return 'A canvas import must name values from compassx/canvas.';
    sawValueImport = true;
  }
  if (!sawValueImport) return 'A canvas imports its components from compassx/canvas.';
  for (const binding of canvasBindings(source)) {
    if (binding.local === 'React' || binding.local === '__kit') {
      return 'This canvas uses a name that is not allowed.';
    }
    if (!ALLOWED.has(binding.imported)) return `A canvas cannot use ${binding.imported}.`;
  }
  if (!/export\s+default\b/.test(source)) return 'A canvas needs a default export.';
  return null;
}

export function stripCanvasImports(source: string): string {
  return source
    .replace(/^\s*import\s+type\s+[\s\S]*?\sfrom\s+['"][^'"]+['"]\s*;?/gm, '')
    .replace(/^\s*import\s+[\s\S]*?\sfrom\s+['"][^'"]+['"]\s*;?/gm, '');
}
