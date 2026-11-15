import assert from 'node:assert/strict';
import { test } from 'node:test';
import { canvasNamesInText, checkCanvasSource, isCanvasFile } from './canvasSourceGate.ts';

const legal = `
import { H1, Stack, Table, BarChart } from "compassx/canvas";

const rows = [["Draft", "2"], ["Done", "4"]];

export default function Page() {
  return (
    <Stack gap={16}>
      <H1>Tasks by stage</H1>
      <Table title="Tasks by stage" columns={["Stage", "Count"]} rows={rows} />
      <BarChart title="Tasks by stage" points={[{ label: "Draft", value: 2 }, { label: "Done", value: 4 }]} />
    </Stack>
  );
}
`;

test('a legal canvas passes the source gate', () => {
  assert.equal(checkCanvasSource(legal), null);
});

test('a foreign import is rejected', () => {
  const source = 'import { useState } from "react";\nexport default function Page() { return null; }\n';
  assert.match(checkCanvasSource(source) || '', /compassx\/canvas/);
});

test('fetch is rejected', () => {
  const source = 'import { Stack } from "compassx/canvas";\nexport default function Page() { return fetch("/secret"); }\n';
  assert.match(checkCanvasSource(source) || '', /not allowed/);
});

test('an unknown component is rejected', () => {
  const source = 'import { NotAComponent } from "compassx/canvas";\nexport default function Page() { return null; }\n';
  assert.match(checkCanvasSource(source) || '', /NotAComponent/);
});

test('only a canvas id after the word canvas becomes a name', () => {
  assert.deepEqual(canvasNamesInText('Sure — what should the new canvas contain?'), []);
  assert.deepEqual(canvasNamesInText('Done — I wrote the canvas session-review.'), ['session-review']);
});

test('canvas files live in .canvases', () => {
  assert.equal(isCanvasFile('.canvases/task-review.canvas.tsx'), true);
  assert.equal(isCanvasFile('src/app.canvas.tsx'), false);
  assert.equal(isCanvasFile('.canvases/nested/task.canvas.tsx'), false);
});
