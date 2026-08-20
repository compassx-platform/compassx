import { useCallback, useRef } from 'react';
import { useNotebookStore } from '../store/notebookStore';
import type { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';

export function useExecuteCell() {
  const kernelRef = useNotebookStore((s) => s.kernelRef);
  const appendOutput = useNotebookStore((s) => s.appendOutput);
  const clearOutput = useNotebookStore((s) => s.clearOutput);
  const setCellRunning = useNotebookStore((s) => s.setCellRunning);
  const setExecutionCount = useNotebookStore((s) => s.setExecutionCount);
  const setVariables = useNotebookStore((s) => s.setVariables);

  const streamBuffer = useRef<Map<string, string>>(new Map());
  const flushTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const flushStreams = useCallback(() => {
    streamBuffer.current.forEach((text, cellId) => {
      if (text) appendOutput(cellId, { type: 'stream', name: 'stdout', text });
    });
    streamBuffer.current.clear();
  }, [appendOutput]);

  const pollVariables = useCallback(
    (kernel: IKernelConnection) => {
      const future = kernel.requestExecute({ code: '%who_ls', store_history: false, silent: true });
      const vars: string[] = [];
      future.onIOPub = (msg) => {
        if (msg.header.msg_type === 'execute_result') {
          const data = (msg.content as Record<string, unknown>).data as Record<string, string>;
          const plain = data?.['text/plain'] ?? '';
          // %who_ls returns a Python list repr like "['a', 'b']"
          const matches = plain.match(/'([^']+)'/g);
          if (matches) vars.push(...matches.map((m) => m.replace(/'/g, '')));
        }
      };
      future.done.then(() => setVariables(vars));
    },
    [setVariables],
  );

  const executeCell = useCallback(
    async (cellId: string, source: string) => {
      const kernel = kernelRef as IKernelConnection | null;
      console.log('[notebook] executeCell called, kernel:', kernel, 'status:', kernel?.status, 'source len:', source.trim().length);
      if (!kernel) {
        console.warn('[notebook] No kernel connected — cannot execute');
        return;
      }
      if (!source.trim()) return;

      clearOutput(cellId);
      setCellRunning(cellId, true);

      flushTimer.current = setInterval(flushStreams, 100);

      const nbPath = useNotebookStore.getState().notebookPath;
      const initCode = nbPath ? `import os; os.environ['COMPASSX_NOTEBOOK_PATH'] = ${JSON.stringify(nbPath)}; os.environ['NOTEBOOK_PATH'] = ${JSON.stringify(nbPath)}\n` : '';
      const future = kernel.requestExecute({ code: initCode + source, store_history: true });
      console.log('[notebook] future created:', future);

      future.onIOPub = (msg) => {
        const msg_type = msg.header.msg_type;
        console.log('[notebook] onIOPub msg_type:', msg_type, msg);
        const content = msg.content as Record<string, unknown>;

        if (msg_type === 'stream') {
          const name = (content.name as string) ?? 'stdout';
          const text = (content.text as string) ?? '';
          if (name === 'stderr') {
            appendOutput(cellId, { type: 'stream', name: 'stderr', text });
          } else {
            streamBuffer.current.set(cellId, (streamBuffer.current.get(cellId) ?? '') + text);
          }
        } else if (msg_type === 'execute_result') {
          flushStreams();
          appendOutput(cellId, {
            type: 'result',
            execution_count: (content.execution_count as number | null) ?? null,
            data: (content.data as Record<string, string>) ?? {},
            metadata: (content.metadata as Record<string, unknown>) ?? {},
          });
        } else if (msg_type === 'display_data') {
          flushStreams();
          appendOutput(cellId, {
            type: 'display',
            data: (content.data as Record<string, string>) ?? {},
            metadata: (content.metadata as Record<string, unknown>) ?? {},
          });
        } else if (msg_type === 'error') {
          flushStreams();
          appendOutput(cellId, {
            type: 'error',
            ename: (content.ename as string) ?? '',
            evalue: (content.evalue as string) ?? '',
            traceback: (content.traceback as string[]) ?? [],
          });
        } else if (msg_type === 'clear_output') {
          flushStreams();
          if (!(content.wait as boolean)) clearOutput(cellId);
        }
      };

      future.onReply = (msg) => {
        console.log('[notebook] onReply:', msg);
        const content = msg.content as unknown;
        const executionContent = content as { execution_count?: number | null };
        setExecutionCount(cellId, executionContent.execution_count ?? null);
      };

      await future.done;
      console.log('[notebook] future.done resolved');

      if (flushTimer.current) {
        clearInterval(flushTimer.current);
        flushTimer.current = null;
      }
      flushStreams();
      setCellRunning(cellId, false);

      // Poll variable list after execution
      pollVariables(kernel);
    },
    [kernelRef, appendOutput, clearOutput, setCellRunning, setExecutionCount, flushStreams, pollVariables],
  );

  return { executeCell };
}
