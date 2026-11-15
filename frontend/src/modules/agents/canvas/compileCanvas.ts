import React from 'react';
import { transform } from 'sucrase';
import { canvasBindings, checkCanvasSource, stripCanvasImports } from './canvasSourceGate';
import * as kit from './kit';

export function compileCanvas(source: string): React.ComponentType {
  const problem = checkCanvasSource(source);
  if (problem) throw new Error(problem);
  const stripped = stripCanvasImports(source);
  const transformed = transform(stripped, {
    transforms: ['typescript', 'jsx'],
    jsxRuntime: 'classic',
    jsxPragma: 'React.createElement',
    jsxFragmentPragma: 'React.Fragment',
    production: true,
  }).code;
  const prelude = canvasBindings(source)
    .map((binding) => `const ${binding.local} = __kit[${JSON.stringify(binding.imported)}];`)
    .join('\n');
  const body = `${prelude}\n${transformed.replace(/export\s+default\s+/, 'return ')}`;
  const factory = new Function('React', '__kit', body) as (react: typeof React, components: typeof kit) => React.ComponentType;
  const component = factory(React, kit);
  if (typeof component !== 'function') throw new Error('A canvas needs a default export.');
  return component;
}
