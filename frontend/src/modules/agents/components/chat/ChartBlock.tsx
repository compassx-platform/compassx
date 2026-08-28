import React from 'react';
import { VegaEmbed } from 'react-vega';

interface ChartBlockProps {
  spec: unknown;
}

export function ChartBlock({ spec }: ChartBlockProps) {
  try {
    return (
      <div style={{ margin: '8px 0', overflowX: 'auto' }}>
        <VegaEmbed
          spec={spec as Parameters<typeof VegaEmbed>[0]['spec']}
          options={{ actions: false }}
          style={{ background: 'transparent' }}
        />
      </div>
    );
  } catch {
    return <pre>{JSON.stringify(spec, null, 2)}</pre>;
  }
}
export default ChartBlock;
