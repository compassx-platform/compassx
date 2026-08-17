import AnsiToHtml from 'ansi-to-html';
import { useMemo } from 'react';

const converter = new AnsiToHtml({ escapeXML: true });

interface Props {
  text: string;
  name: 'stdout' | 'stderr';
}

export default function StreamOutput({ text, name }: Props) {
  const html = useMemo(() => converter.toHtml(text), [text]);
  return (
    <pre
      className={`notebook-output-stream ${name === 'stderr' ? 'notebook-output-stderr' : ''}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
