import type { Cell, CellOutput } from '../store/notebookStore';

// ── nbformat v4 types (minimal) ────────────────────────────────────────────

interface NbOutput {
  output_type: string;
  [key: string]: unknown;
}

interface NbCell {
  id: string;
  cell_type: 'code' | 'markdown' | 'raw';
  source: string | string[];
  metadata: Record<string, unknown>;
  outputs?: NbOutput[];
  execution_count?: number | null;
}

interface Notebook {
  nbformat: 4;
  nbformat_minor: 5;
  metadata: Record<string, unknown>;
  cells: NbCell[];
}

// ── helpers ────────────────────────────────────────────────────────────────

function joinSource(src: string | string[]): string {
  return Array.isArray(src) ? src.join('') : src;
}

function toNbOutput(out: CellOutput): NbOutput {
  if (out.type === 'stream') {
    return { output_type: 'stream', name: out.name, text: out.text };
  }
  if (out.type === 'result') {
    return {
      output_type: 'execute_result',
      execution_count: out.execution_count,
      data: out.data,
      metadata: out.metadata,
    };
  }
  if (out.type === 'display') {
    return { output_type: 'display_data', data: out.data, metadata: out.metadata };
  }
  // error
  return {
    output_type: 'error',
    ename: (out as { ename: string }).ename,
    evalue: (out as { evalue: string }).evalue,
    traceback: (out as { traceback: string[] }).traceback,
  };
}

function fromNbOutput(out: NbOutput): CellOutput | null {
  if (out.output_type === 'stream') {
    return { type: 'stream', name: (out.name as 'stdout' | 'stderr') ?? 'stdout', text: joinSource(out.text as string) };
  }
  if (out.output_type === 'execute_result') {
    return {
      type: 'result',
      execution_count: (out.execution_count as number | null) ?? null,
      data: (out.data as Record<string, string>) ?? {},
      metadata: (out.metadata as Record<string, unknown>) ?? {},
    };
  }
  if (out.output_type === 'display_data') {
    return {
      type: 'display',
      data: (out.data as Record<string, string>) ?? {},
      metadata: (out.metadata as Record<string, unknown>) ?? {},
    };
  }
  if (out.output_type === 'error') {
    return {
      type: 'error',
      ename: (out.ename as string) ?? '',
      evalue: (out.evalue as string) ?? '',
      traceback: (out.traceback as string[]) ?? [],
    };
  }
  return null;
}

// ── Public API ──────────────────────────────────────────────────────────────

export function serialize(cells: Cell[], metadata: Record<string, unknown> = {}): Notebook {
  return {
    nbformat: 4,
    nbformat_minor: 5,
    metadata: {
      kernelspec: { display_name: 'Python 3', language: 'python', name: 'python3' },
      language_info: { name: 'python' },
      ...metadata,
    },
    cells: cells.map((c) => {
      const nbCellMetadata: Record<string, unknown> = c.title ? { title: c.title } : {};
      if (c.cellStatus) nbCellMetadata.cellStatus = c.cellStatus;
      if (c.committedSource !== undefined) nbCellMetadata.committedSource = c.committedSource;
      if (c.pendingSource !== undefined) nbCellMetadata.pendingSource = c.pendingSource;

      const nbCell: NbCell = {
        id: c.id,
        cell_type: c.type,
        source: c.source,
        metadata: nbCellMetadata,
      };
      if (c.type === 'code') {
        nbCell.outputs = c.outputs.map(toNbOutput);
        nbCell.execution_count = c.executionCount;
      }
      return nbCell;
    }),
  };
}

export function deserialize(nb: Notebook): Cell[] {
  const cells = (nb.cells || []).map((nbCell) => {
    const metadata = nbCell.metadata || {};
    const cellStatus = (metadata.cellStatus as 'clean' | 'pending') ?? 'clean';
    const committedSource = (metadata.committedSource as string) ?? undefined;
    const pendingSource = (metadata.pendingSource as string) ?? undefined;
    const source = joinSource(nbCell.source);
    
    let pendingAgentEdit = undefined;
    if (cellStatus === 'pending') {
      pendingAgentEdit = {
        action: 'replace_cell' as const,
        originalSource: committedSource ?? source,
        proposedSource: source,
        cellType: nbCell.cell_type,
        createdCell: committedSource === undefined || committedSource === '',
      };
    }

    return {
      id: nbCell.id ?? Math.random().toString(36).slice(2, 10),
      type: nbCell.cell_type,
      source,
      committedSource,
      pendingSource,
      cellStatus,
      pendingAgentEdit,
      outputs: (nbCell.outputs ?? []).map(fromNbOutput).filter(Boolean) as CellOutput[],
      executionCount: nbCell.execution_count ?? null,
      isRunning: false,
      title: (metadata.title as string) ?? undefined,
    };
  });

  if (cells.length === 0) {
    return [
      {
        id: Math.random().toString(36).slice(2, 10),
        type: 'code',
        source: '',
        outputs: [],
        executionCount: null,
        isRunning: false,
        cellStatus: 'clean',
      },
    ];
  }

  return cells;
}
