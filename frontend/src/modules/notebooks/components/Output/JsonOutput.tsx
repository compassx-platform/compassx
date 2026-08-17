import { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';

interface NodeProps {
  value: unknown;
  depth?: number;
}

function JsonNode({ value, depth = 0 }: NodeProps) {
  const [open, setOpen] = useState(depth < 2);

  if (value === null) return <span className="json-null">null</span>;
  if (typeof value === 'boolean') return <span className="json-bool">{String(value)}</span>;
  if (typeof value === 'number') return <span className="json-num">{value}</span>;
  if (typeof value === 'string') return <span className="json-str">"{value}"</span>;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="json-bracket">[]</span>;
    return (
      <span>
        <button className="json-toggle" onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </button>
        <span className="json-bracket">[</span>
        {open ? (
          <div style={{ paddingLeft: 16 }}>
            {value.map((v, i) => (
              <div key={i}><JsonNode value={v} depth={depth + 1} />{i < value.length - 1 ? ',' : ''}</div>
            ))}
          </div>
        ) : <span className="json-ellipsis">…{value.length} items</span>}
        <span className="json-bracket">]</span>
      </span>
    );
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value as object);
    if (keys.length === 0) return <span className="json-bracket">{'{}'}</span>;
    return (
      <span>
        <button className="json-toggle" onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </button>
        <span className="json-bracket">{'{'}</span>
        {open ? (
          <div style={{ paddingLeft: 16 }}>
            {keys.map((k, i) => (
              <div key={k}>
                <span className="json-key">"{k}"</span>
                <span className="json-colon">: </span>
                <JsonNode value={(value as Record<string, unknown>)[k]} depth={depth + 1} />
                {i < keys.length - 1 ? ',' : ''}
              </div>
            ))}
          </div>
        ) : <span className="json-ellipsis">…{keys.length} keys</span>}
        <span className="json-bracket">{'}'}</span>
      </span>
    );
  }

  return <span>{String(value)}</span>;
}

interface Props {
  data: string;
}

export default function JsonOutput({ data }: Props) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    return <pre className="notebook-output-text">{data}</pre>;
  }
  return (
    <div className="notebook-output-json">
      <JsonNode value={parsed} />
    </div>
  );
}
