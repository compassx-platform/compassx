import { Check, X } from 'lucide-react';
import { useNotebookStore, type AgentCellEditProposal } from '../../store/notebookStore';

interface Props {
  cellId: string;
  proposal: AgentCellEditProposal;
}

type DiffLine = {
  kind: 'context' | 'added' | 'removed';
  text: string;
};

function splitLines(source: string) {
  return source.length ? source.split('\n') : [];
}

function buildDiff(originalSource: string, proposedSource: string): DiffLine[] {
  const original = splitLines(originalSource);
  const proposed = splitLines(proposedSource);
  let prefix = 0;
  while (prefix < original.length && prefix < proposed.length && original[prefix] === proposed[prefix]) {
    prefix += 1;
  }

  let originalSuffix = original.length - 1;
  let proposedSuffix = proposed.length - 1;
  while (
    originalSuffix >= prefix &&
    proposedSuffix >= prefix &&
    original[originalSuffix] === proposed[proposedSuffix]
  ) {
    originalSuffix -= 1;
    proposedSuffix -= 1;
  }

  const lines: DiffLine[] = [];
  original.slice(0, prefix).forEach((text) => lines.push({ kind: 'context', text }));
  original.slice(prefix, originalSuffix + 1).forEach((text) => lines.push({ kind: 'removed', text }));
  proposed.slice(prefix, proposedSuffix + 1).forEach((text) => lines.push({ kind: 'added', text }));
  original.slice(originalSuffix + 1).forEach((text) => lines.push({ kind: 'context', text }));
  return lines.length ? lines : [{ kind: 'context', text: '' }];
}

export default function AgentEditDiff({ cellId, proposal }: Props) {
  const acceptAgentCellEdit = useNotebookStore((s) => s.acceptAgentCellEdit);
  const rejectAgentCellEdit = useNotebookStore((s) => s.rejectAgentCellEdit);
  const diff = buildDiff(proposal.originalSource, proposal.proposedSource);

  return (
    <div className="notebook-agent-diff" onClick={(event) => event.stopPropagation()}>
      <div className="notebook-agent-diff-header">
        <div>
          <strong>Agent proposed a change</strong>
          {proposal.explanation && <span>{proposal.explanation}</span>}
        </div>
        <div className="notebook-agent-diff-actions">
          <button type="button" className="notebook-agent-accept" onClick={() => acceptAgentCellEdit(cellId)} title="Accept change">
            <Check size={14} />
            Accept
          </button>
          <button type="button" className="notebook-agent-reject" onClick={() => rejectAgentCellEdit(cellId)} title="Reject change">
            <X size={14} />
            Reject
          </button>
        </div>
      </div>
      <pre className="notebook-agent-diff-body">
        {diff.map((line, index) => (
          <div key={`${line.kind}-${index}`} className={`notebook-agent-diff-line is-${line.kind}`}>
            <span className="notebook-agent-diff-marker">
              {line.kind === 'added' ? '+' : line.kind === 'removed' ? '-' : ' '}
            </span>
            <code>{line.text || ' '}</code>
          </div>
        ))}
      </pre>
    </div>
  );
}
