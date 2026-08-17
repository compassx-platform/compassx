import AnsiToHtml from 'ansi-to-html';
import { useMemo } from 'react';

const converter = new AnsiToHtml({ escapeXML: true });

interface Props {
  ename: string;
  evalue: string;
  traceback: string[];
}

export default function ErrorOutput({ ename, evalue, traceback }: Props) {
  const traceHtml = useMemo(
    () => traceback.map((line) => converter.toHtml(line)).join('\n'),
    [traceback],
  );

  return (
    <div className="notebook-output-error">
      <div className="notebook-output-error-title">
        <span className="notebook-output-error-name">{ename}</span>
        {evalue && <span className="notebook-output-error-value">: {evalue}</span>}
      </div>
      <pre
        className="notebook-output-traceback"
        dangerouslySetInnerHTML={{ __html: traceHtml }}
      />
    </div>
  );
}
