import type { CellOutput as CellOutputType } from '../../store/notebookStore';
import StreamOutput from '../Output/StreamOutput';
import RichOutput from '../Output/RichOutput';
import ErrorOutput from '../Output/ErrorOutput';

interface Props {
  outputs: CellOutputType[];
}

export default function CellOutput({ outputs }: Props) {
  if (outputs.length === 0) return null;

  return (
    <div className="notebook-cell-outputs">
      {outputs.map((out, i) => {
        if (out.type === 'stream') {
          return <StreamOutput key={i} text={out.text} name={out.name} />;
        }
        if (out.type === 'result' || out.type === 'display') {
          return <RichOutput key={i} data={out.data} />;
        }
        if (out.type === 'error') {
          return <ErrorOutput key={i} ename={out.ename} evalue={out.evalue} traceback={out.traceback} />;
        }
        return null;
      })}
    </div>
  );
}
