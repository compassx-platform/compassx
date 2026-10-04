export const CODE_FONT_SIZE_DEFAULT = 13;
export const CODE_FONT_SIZE_MIN = 10;
export const CODE_FONT_SIZE_MAX = 24;
export const CODE_FONT_SIZE_STEP = 1;

export const CODE_FONT_WEIGHT_NORMAL = 400;
export const CODE_FONT_WEIGHT_HEAVIER = 500;
export const CODE_FONT_WEIGHT_DEFAULT = CODE_FONT_WEIGHT_NORMAL;
export type CodeFontWeight = typeof CODE_FONT_WEIGHT_NORMAL | typeof CODE_FONT_WEIGHT_HEAVIER;

export const CODE_FONT_FAMILY_DEFAULT = '';

export const CODE_FONT_FAMILY_FALLBACK =
  "'Geist Mono Variable', 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

export interface CodeFont {
  sizePx: number;
  family: string;
  weight: CodeFontWeight;
}

const STORAGE_KEY_SIZE = 'compassx:code-font-size';
const STORAGE_KEY_FAMILY = 'compassx:code-font-family';
const STORAGE_KEY_WEIGHT = 'compassx:code-font-weight';

const subscribers = new Set<(font: CodeFont) => void>();

export function clampCodeFontSizePx(px: number): number {
  return Math.min(CODE_FONT_SIZE_MAX, Math.max(CODE_FONT_SIZE_MIN, Math.round(px)));
}

export function readCodeFont(): CodeFont {
  if (typeof window === 'undefined') {
    return {
      sizePx: CODE_FONT_SIZE_DEFAULT,
      family: CODE_FONT_FAMILY_DEFAULT,
      weight: CODE_FONT_WEIGHT_DEFAULT,
    };
  }
  try {
    const rawSize = window.localStorage.getItem(STORAGE_KEY_SIZE);
    const sizePx = rawSize ? clampCodeFontSizePx(Number(rawSize)) : CODE_FONT_SIZE_DEFAULT;
    const rawFamily = window.localStorage.getItem(STORAGE_KEY_FAMILY);
    const family = rawFamily ?? CODE_FONT_FAMILY_DEFAULT;
    const rawWeight = window.localStorage.getItem(STORAGE_KEY_WEIGHT);
    const weight = rawWeight === '500' ? CODE_FONT_WEIGHT_HEAVIER : CODE_FONT_WEIGHT_NORMAL;
    return { sizePx, family, weight };
  } catch {
    return {
      sizePx: CODE_FONT_SIZE_DEFAULT,
      family: CODE_FONT_FAMILY_DEFAULT,
      weight: CODE_FONT_WEIGHT_DEFAULT,
    };
  }
}

export function codeFontFamilyForEditor(family: string): string {
  if (!family || !family.trim()) return CODE_FONT_FAMILY_FALLBACK;
  return `"${family}", ${CODE_FONT_FAMILY_FALLBACK}`;
}

export function subscribeCodeFont(listener: (font: CodeFont) => void): () => void {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
}
