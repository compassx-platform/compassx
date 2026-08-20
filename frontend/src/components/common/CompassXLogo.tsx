import React from 'react';

interface CompassXLogoProps {
  size?: number;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * CompassX - Clean Geometric Compass Logo
 * - Thick circular bezel with 4 pronounced 90° cardinal gaps (at 12, 3, 6, and 9 o'clock)
 * - 45° tilted diamond needle: Full unified outer stroke ensuring 100% identical size for both halves
 *   (Top-Right half solid filled, Bottom-Left half hollow outline)
 */
export function CompassXLogo({
  size = 26,
  color = 'currentColor',
  className,
  style,
}: CompassXLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ flexShrink: 0, display: 'block', ...style }}
    >
      {/* 4 Thick Circular Quadrant Arcs with Pronounced Cardinal Gaps (R = 36, Stroke = 9) */}
      {/* Top-Right Quadrant Arc */}
      <path
        d="M 58.1 14.9 A 36 36 0 0 1 85.1 41.9"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
      />
      {/* Bottom-Right Quadrant Arc */}
      <path
        d="M 85.1 58.1 A 36 36 0 0 1 58.1 85.1"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
      />
      {/* Bottom-Left Quadrant Arc */}
      <path
        d="M 41.9 85.1 A 36 36 0 0 1 14.9 58.1"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
      />
      {/* Top-Left Quadrant Arc */}
      <path
        d="M 14.9 41.9 A 36 36 0 0 1 41.9 14.9"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
      />

      {/* Center 45° Diamond Needle - Unified 1:1 Symmetrical Geometry */}
      {/* Top-Right Solid Filled Half */}
      <polygon
        points="68,32 56.5,56.5 43.5,43.5"
        fill={color}
      />

      {/* Unified Needle Outer Border (ensures 100% identical size, thickness, and boundary for both halves) */}
      <polygon
        points="68,32 56.5,56.5 32,68 43.5,43.5"
        fill="none"
        stroke={color}
        strokeWidth="3.2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* Center Dividing Waist Line */}
      <line
        x1="43.5"
        y1="43.5"
        x2="56.5"
        y2="56.5"
        stroke={color}
        strokeWidth="3.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default CompassXLogo;
