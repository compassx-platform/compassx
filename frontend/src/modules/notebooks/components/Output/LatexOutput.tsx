import { useMemo } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface Props {
  latex: string;
}

export default function LatexOutput({ latex }: Props) {
  const html = useMemo(() => {
    // Strip surrounding $$ or $ delimiters if present
    const clean = latex.replace(/^\$\$?([\s\S]*?)\$\$?$/, '$1').trim();
    try {
      return katex.renderToString(clean, { throwOnError: false, displayMode: true });
    } catch {
      return `<pre>${latex}</pre>`;
    }
  }, [latex]);

  return <div className="notebook-output-latex" dangerouslySetInnerHTML={{ __html: html }} />;
}
