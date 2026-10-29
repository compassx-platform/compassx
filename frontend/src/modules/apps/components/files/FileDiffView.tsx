import { Loader2 } from 'lucide-react';
import { useDevFileDiff } from '../../hooks/useApps';

interface FileDiffViewProps {
  appId: string;
  path: string;
  workspaceId?: string;
}

function lineClass(line: string): string {
  if (line.startsWith('@@')) return 'bg-sky-50 text-sky-800';
  if (
    line.startsWith('diff ') ||
    line.startsWith('index ') ||
    line.startsWith('---') ||
    line.startsWith('+++')
  ) {
    return 'text-neutral-400';
  }
  if (line.startsWith('+')) return 'bg-emerald-50 text-emerald-900';
  if (line.startsWith('-')) return 'bg-rose-50 text-rose-900';
  return 'text-neutral-700';
}

export function FileDiffView({ appId, path, workspaceId }: FileDiffViewProps) {
  const { data, isLoading, isError } = useDevFileDiff(appId, path, workspaceId, true);
  const patch = data?.patch || '';
  const lines = patch ? patch.split('\n') : [];

  if (isLoading && !patch) {
    return (
      <div className="flex h-48 flex-col items-center justify-center gap-2 text-neutral-400">
        <Loader2 className="size-5 animate-spin text-neutral-500" />
        <span className="text-xs font-mono">Loading diff...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-48 items-center justify-center px-4 text-center text-xs font-mono text-rose-600">
        Could not load the diff for this file.
      </div>
    );
  }

  if (!patch.trim()) {
    return (
      <div className="flex h-48 items-center justify-center px-4 text-center text-xs font-mono text-neutral-500">
        No line changes against the last commit.
      </div>
    );
  }

  return (
    <pre className="m-0 min-h-full p-3 font-mono text-[12px] leading-5 whitespace-pre-wrap break-all">
      {lines.map((line, index) => (
        <div key={`${index}-${line.slice(0, 24)}`} className={lineClass(line)}>
          {line || ' '}
        </div>
      ))}
    </pre>
  );
}
