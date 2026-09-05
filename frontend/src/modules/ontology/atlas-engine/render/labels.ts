/**
 * Node label paint — ported from the B2+ prototype's `drawTracked()`/
 * `drawLabel()` (`docs/prototypes/topology-b2plus.html` §12-13).
 */

import { smoothstep } from "../model/altitude";
import { HITTABLE_MIN_TIER_ALPHA } from "../model/tier-visibility";

export interface LabelDrawState {
  kind: "org" | "project" | "domain" | "subdomain" | "capability" | "element" | string;
  text: string;
  screenX: number;
  screenY: number;
  /** World-space node radius × camera.scale (used to offset label below the node). */
  screenRadius: number;
  egoState: "center" | "neighbor" | "dim" | "normal";
  /** Whether this node is the currently-hovered node (no focus active). Floors its label to full contrast, same as `egoState === "center"`. */
  isHovered: boolean;
  /** The node's own effective/tier alpha this frame (`model/tier-visibility.ts#effectiveNodeAlpha`) — ties capability/element label eligibility to "if you can click it, you can read it". Ignored by project/domain. */
  revealAlpha: number;
  /**
   * W6 agent visibility — true when this label belongs to the agent
   * heartbeat's current focus node (mirrors `NodeShapeDrawState.agentFocus`
   * in `render/node-shapes.ts`). Draws a small amber `drawActivityMark` dot
   * just past the label's own text.
   */
  agentFocus: boolean;
  /** Label zoom factor (`labelZoomScale(cameraScale)`), default 1. */
  fontScale?: number;
  /**
   * LOD presence, 0..1 (default 1).
   */
  presenceAlpha?: number;
  /**
   * The baseline the placer settled on.
   */
  baselineY?: number;
}

export interface LabelTokens {
  labelProject: string;
  labelDomain: string;
  labelCapability: string;
  labelElement: string;
  /** W6 agent visibility — amber signal tone. */
  amberHub: string;
}

/** Approximate glyph height per kind (px) — used to build the label bbox for greedy suppression. */
const LABEL_FONT_SIZE: Record<string, number> = {
  org: 15,
  project: 15,
  domain: 10,
  subdomain: 10.5,
  capability: 10.5,
  element: 9.5,
};

/** Font weights for assembling the scaled font string. */
const LABEL_FONT_WEIGHT: Record<string, number> = {
  org: 600,
  project: 600,
  domain: 600,
  subdomain: 500,
  capability: 500,
  element: 400,
};

const LABEL_FONT_FAMILY = "-apple-system, 'SF Pro Text', sans-serif";

/**
 * Label zoom factor: a sublinear (exponent 0.4) function of camera zoom, capped
 * to [1, 1.9].
 */
export function labelZoomScale(cameraScale: number): number {
  if (!Number.isFinite(cameraScale) || cameraScale <= 1) return 1;
  return Math.min(1.9, Math.pow(cameraScale, 0.4));
}

/** Scaled font size, quantised to 0.5px — shared by the widthCache key and the paint. */
export function scaledLabelFontSize(kind: string, scale: number): number {
  return Math.round((LABEL_FONT_SIZE[kind] ?? 9.5) * scale * 2) / 2;
}

/** Scaled font string. */
function scaledLabelFont(kind: string, scale: number): string {
  return `${LABEL_FONT_WEIGHT[kind] ?? 400} ${scaledLabelFontSize(kind, scale)}px ${LABEL_FONT_FAMILY}`;
}

/**
 * Manual letter-tracking for the instrument caption's tracked caps
 */
const DOMAIN_TRACKING = 1.6;

const widthCache = new Map<string, number>();

function measureLabelWidthUncached(
  ctx: CanvasRenderingContext2D,
  kind: string,
  text: string,
  scale: number,
): number {
  ctx.font = scaledLabelFont(kind, scale);
  return ctx.measureText(text).width;
}

export function measureLabelWidth(
  ctx: CanvasRenderingContext2D,
  kind: string,
  text: string,
  scale = 1,
): number {
  const key = `${kind}|${scaledLabelFontSize(kind, scale)}|${text}`;
  const cached = widthCache.get(key);
  if (cached !== undefined) return cached;
  const width = measureLabelWidthUncached(ctx, kind, text, scale);
  widthCache.set(key, width);
  return width;
}

const CHILD_LABEL_REVEAL_MIN = HITTABLE_MIN_TIER_ALPHA;
const CHILD_LABEL_REVEAL_FULL = 0.85;

export interface LabelVerticalMetrics {
  /** Pixels to reserve **above** the baseline. */
  ascent: number;
  /** Pixels to reserve **below** the baseline. */
  descent: number;
}

const verticalMetricsCache = new Map<string, LabelVerticalMetrics>();

function approximateVerticalMetrics(fontSize: number): LabelVerticalMetrics {
  return { ascent: fontSize, descent: 2 };
}

export function measureLabelVerticalMetrics(
  ctx: CanvasRenderingContext2D,
  kind: string,
  scale = 1,
): LabelVerticalMetrics {
  const fontSize = scaledLabelFontSize(kind, scale);
  const key = `${kind}|${fontSize}`;
  const cached = verticalMetricsCache.get(key);
  if (cached !== undefined) return cached;

  let metrics = approximateVerticalMetrics(fontSize);
  try {
    ctx.font = scaledLabelFont(kind, scale);
    const m = ctx.measureText("가Ag");
    const ascent = m.fontBoundingBoxAscent;
    const descent = m.fontBoundingBoxDescent;
    if (typeof ascent === "number" && typeof descent === "number" && ascent > 0 && descent > 0) {
      metrics = { ascent, descent };
    }
  } catch {
    // Fallback if measurement fails
  }
  verticalMetricsCache.set(key, metrics);
  return metrics;
}

export interface LabelAlphaInput {
  kind: string;
  egoState: LabelDrawState["egoState"];
  isHovered: boolean;
  revealAlpha: number;
}

export function computeLabelAlpha(input: LabelAlphaInput): number {
  const { kind, egoState, isHovered, revealAlpha } = input;
  if (egoState === "dim") return 0;
  if (egoState === "center" || isHovered) return 1;

  if (kind === "org" || kind === "project" || kind === "domain") return 1;
  return smoothstep(CHILD_LABEL_REVEAL_MIN, CHILD_LABEL_REVEAL_FULL, revealAlpha);
}

export const ACTIVITY_MARK_RADIUS = 2.4;
export const ACTIVITY_MARK_GAP = 5;

function drawActivityMark(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  color: string,
  alpha: number,
): void {
  if (alpha <= 0.02) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  ctx.arc(x, y, ACTIVITY_MARK_RADIUS, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.restore();
}

/** Screen-Y offset below the node's own radius, per kind */
export const LABEL_OFFSET: Record<string, number> = {
  org: 20,
  project: 20,
  domain: 17,
  subdomain: 13,
  capability: 13,
  element: 13,
};

export const LABEL_NODE_OUTLINE_ALLOWANCE = 6;
export const LABEL_NODE_CLEARANCE = 3;

export function resolveLabelBaselineY(
  kind: string,
  screenY: number,
  screenRadius: number,
  fontScale = 1,
): number {
  const outlineBottom = screenY + screenRadius + LABEL_NODE_OUTLINE_ALLOWANCE;
  const offset = LABEL_OFFSET[kind] ?? 13;
  const byOffset = screenY + screenRadius + offset * fontScale;
  const byGlyphTop = outlineBottom + LABEL_NODE_CLEARANCE + scaledLabelFontSize(kind, fontScale);
  return Math.max(byOffset, byGlyphTop);
}

export function resolveFlippedLabelBaselineY(
  screenY: number,
  screenRadius: number,
): number {
  return screenY - screenRadius - LABEL_NODE_OUTLINE_ALLOWANCE - LABEL_NODE_CLEARANCE;
}

function drawTrackedText(
  ctx: CanvasRenderingContext2D,
  text: string,
  cx: number,
  cy: number,
  color: string,
  tracking: number,
  alpha: number,
): void {
  const widths: number[] = [];
  let total = 0;
  for (let i = 0; i < text.length; i += 1) {
    const width = ctx.measureText(text[i]).width;
    widths.push(width);
    total += width + (i < text.length - 1 ? tracking : 0);
  }
  let x = cx - total / 2;
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = color;
  ctx.globalAlpha = alpha;
  for (let i = 0; i < text.length; i += 1) {
    ctx.fillText(text[i], x, cy);
    x += widths[i] + tracking;
  }
  ctx.globalAlpha = 1;
}

export function drawInstrumentCaption(
  ctx: CanvasRenderingContext2D,
  text: string,
  cx: number,
  cy: number,
  color: string,
  alpha: number,
): void {
  if (alpha <= 0.02) return;
  ctx.font = scaledLabelFont("domain", 1);
  drawTrackedText(ctx, text.toUpperCase(), cx, cy, color, DOMAIN_TRACKING, alpha);
}

export function draw(ctx: CanvasRenderingContext2D, state: LabelDrawState, tokens: LabelTokens): void {
  const { kind, text, screenX: x, screenY: y, screenRadius: r, egoState, isHovered, revealAlpha, agentFocus } = state;
  const fontScale = state.fontScale ?? 1;
  const presenceAlpha = Math.min(1, Math.max(0, state.presenceAlpha ?? 1));
  const ty = state.baselineY ?? resolveLabelBaselineY(kind, y, r, fontScale);

  const alpha = computeLabelAlpha({ kind, egoState, isHovered, revealAlpha }) * presenceAlpha;
  if (alpha <= 0.02) return;

  if (kind === "org" || kind === "project") {
    ctx.font = scaledLabelFont("project", fontScale);
    ctx.fillStyle = tokens.labelProject;
  } else if (kind === "domain") {
    ctx.font = scaledLabelFont("domain", fontScale);
    ctx.fillStyle = tokens.labelDomain;
  } else if (kind === "subdomain" || kind === "capability") {
    ctx.font = scaledLabelFont("capability", fontScale);
    ctx.fillStyle = tokens.labelCapability;
  } else {
    ctx.font = scaledLabelFont("element", fontScale);
    ctx.fillStyle = tokens.labelElement;
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  ctx.globalAlpha = alpha;
  ctx.fillText(text, x, ty);
  ctx.globalAlpha = 1;

  if (agentFocus) {
    const width = measureLabelWidth(ctx, kind, text, fontScale);
    drawActivityMark(ctx, x + width / 2 + ACTIVITY_MARK_GAP, ty - scaledLabelFontSize(kind, fontScale) * 0.35, tokens.amberHub, alpha);
  }
}
