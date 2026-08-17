import React, { useState } from 'react';

// G2-G4: Inline asset chip rendered wherever the model emits an <asset> tag.
// Clicking navigates to the canonical catalog URL.
// Hovering triggers a lazy fetch for a preview card.

export type AssetObjectType =
  | 'notebook' | 'table' | 'dashboard' | 'volume'
  | 'job' | 'app' | 'query' | 'unknown';

export interface AssetChipProps {
  fullName: string;           // catalog.schema.object
  objectType: AssetObjectType;
  displayName?: string;       // defaults to last segment of fullName
  className?: string;
}

const TYPE_ICON: Record<string, string> = {
  notebook:  '📓',
  table:     '🗃️',
  dashboard: '📊',
  volume:    '💾',
  job:       '⚙️',
  app:       '📱',
  query:     '🔍',
  unknown:   '🔗',
};

const TYPE_COLOR: Record<string, string> = {
  notebook:  'var(--chip-notebook, #7c3aed)',
  table:     'var(--chip-table, #0891b2)',
  dashboard: 'var(--chip-dashboard, #059669)',
  volume:    'var(--chip-volume, #d97706)',
  job:       'var(--chip-job, #dc2626)',
  app:       'var(--chip-app, #db2777)',
  query:     'var(--chip-query, #4f46e5)',
  unknown:   'var(--chip-unknown, #6b7280)',
};

/** G4: canonical URL resolver */
function resolveAssetUrl(fullName: string, objectType: string): string {
  const parts = fullName.split('.');
  if (parts.length === 3) {
    const [catalog, schema, obj] = parts;
    return `/catalog/${catalog}/${schema}/${obj}?type=${objectType}`;
  }
  if (parts.length === 2) {
    const [schema, obj] = parts;
    return `/catalog/${schema}/${obj}?type=${objectType}`;
  }
  return `/catalog?q=${encodeURIComponent(fullName)}`;
}

export const AssetChip: React.FC<AssetChipProps> = ({
  fullName,
  objectType,
  displayName,
  className = '',
}) => {
  const [hoverPreview, setHoverPreview] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const label = displayName ?? fullName.split('.').pop() ?? fullName;
  const icon  = TYPE_ICON[objectType] ?? TYPE_ICON.unknown;
  const color = TYPE_COLOR[objectType] ?? TYPE_COLOR.unknown;
  const href  = resolveAssetUrl(fullName, objectType);

  // G3 Hover: lazy fetch preview
  const handleMouseEnter = async () => {
    if (hoverPreview !== null || loadingPreview) return;
    setLoadingPreview(true);
    try {
      const res = await fetch(`/api/v1/catalog/asset-preview?full_name=${encodeURIComponent(fullName)}&type=${objectType}`);
      if (res.ok) {
        const data = await res.json();
        setHoverPreview(data.preview ?? data.description ?? fullName);
      }
    } catch {
      setHoverPreview(fullName);
    } finally {
      setLoadingPreview(false);
    }
  };

  return (
    <span
      className={`asset-chip ${className}`}
      title={hoverPreview ?? (loadingPreview ? 'Loading…' : fullName)}
      onMouseEnter={handleMouseEnter}
      style={{ '--chip-color': color } as React.CSSProperties}
    >
      <a
        href={href}
        onClick={e => { e.preventDefault(); window.location.href = href; }}
        className="asset-chip__link"
      >
        <span className="asset-chip__icon">{icon}</span>
        <span className="asset-chip__label">{label}</span>
        <span className="asset-chip__type">{objectType}</span>
      </a>

      <style>{`
        .asset-chip {
          display: inline-flex;
          align-items: center;
          vertical-align: middle;
          border-radius: 6px;
          border: 1px solid var(--chip-color);
          background: color-mix(in srgb, var(--chip-color) 12%, transparent);
          font-size: 0.78rem;
          line-height: 1;
          overflow: hidden;
          position: relative;
          transition: box-shadow 0.15s ease, transform 0.1s ease;
          cursor: pointer;
          user-select: none;
        }
        .asset-chip:hover {
          box-shadow: 0 0 0 2px color-mix(in srgb, var(--chip-color) 35%, transparent);
          transform: translateY(-1px);
        }
        .asset-chip__link {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 3px 8px 3px 6px;
          text-decoration: none;
          color: var(--chip-color);
          font-weight: 500;
        }
        .asset-chip__icon {
          font-size: 0.85em;
        }
        .asset-chip__label {
          font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
          max-width: 180px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .asset-chip__type {
          font-size: 0.68em;
          opacity: 0.65;
          text-transform: uppercase;
          letter-spacing: 0.03em;
          border-left: 1px solid var(--chip-color);
          padding-left: 5px;
          margin-left: 2px;
        }
      `}</style>
    </span>
  );
};

/** Parse the model's <asset ref="..." type="...">label</asset> tags from a text string
 *  and return an array of segments (plain string | AssetChipProps).
 *  Unresolvable refs (no match in knownNames set) are returned as plain text. */
export function parseAssetTags(
  text: string,
  knownNames?: Set<string>,
): Array<string | { chip: AssetChipProps }> {
  const ASSET_RE = /<asset\s+ref="([^"]+)"\s+type="([^"]+)">(.*?)<\/asset>/g;
  const rawSegments: Array<string | { chip: AssetChipProps }> = [];
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = ASSET_RE.exec(text)) !== null) {
    if (m.index > last) rawSegments.push(text.slice(last, m.index));
    const [, fullName, objectType, label] = m;
    const shouldResolve = !knownNames || knownNames.size === 0 || knownNames.has(fullName) || fullName.includes('.');
    if (shouldResolve) {
      rawSegments.push({ chip: { fullName, objectType: objectType as AssetObjectType, displayName: label } });
    } else {
      rawSegments.push(label);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) rawSegments.push(text.slice(last));

  // Second pass: scan text segments for known asset names or backticked dotted names (e.g. `solar_ecg.scada.name`)
  const finalSegments: Array<string | { chip: AssetChipProps }> = [];
  for (const seg of rawSegments) {
    if (typeof seg !== 'string') {
      finalSegments.push(seg);
      continue;
    }

    // Match backticked `catalog.schema.object` or raw dotted names if in knownNames or 3-part dotted pattern
    const PATH_RE = /`?([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)`?/g;
    let sLast = 0;
    let pm: RegExpExecArray | null;
    let matchedAny = false;

    while ((pm = PATH_RE.exec(seg)) !== null) {
      const fullMatch = pm[0];
      const assetPath = pm[1];
      if (knownNames && knownNames.size > 0 && !knownNames.has(assetPath)) {
        continue;
      }
      matchedAny = true;
      if (pm.index > sLast) finalSegments.push(seg.slice(sLast, pm.index));
      const inferredType: AssetObjectType =
        assetPath.includes('notebook') ? 'notebook' :
        assetPath.includes('dash') ? 'dashboard' : 'table';
      finalSegments.push({ chip: { fullName: assetPath, objectType: inferredType, displayName: assetPath.split('.').pop() } });
      sLast = pm.index + fullMatch.length;
    }

    if (!matchedAny) {
      finalSegments.push(seg);
    } else if (sLast < seg.length) {
      finalSegments.push(seg.slice(sLast));
    }
  }

  return finalSegments;
}
