import React, { useEffect, useRef, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CopyPathButtonProps {
  path: string;
  label?: string;
  revealOnHover?: boolean;
}

export function CopyPathButton({
  path,
  label = 'Copy path',
  revealOnHover = false,
}: CopyPathButtonProps) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<number>(0);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, []);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (timerRef.current) window.clearTimeout(timerRef.current);
    try {
      await navigator.clipboard.writeText(path);
      setCopied(true);
      timerRef.current = window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const filename = path.split('/').filter(Boolean).pop() ?? path;

  return (
    <button
      type="button"
      title={`${label}: ${filename}`}
      aria-label={`${label}: ${filename}`}
      onClick={handleClick}
      className={cn(
        'inline-flex size-[20px] items-center justify-center rounded p-0.5 text-neutral-400 transition-all hover:bg-neutral-100 hover:text-neutral-900',
        copied && 'text-emerald-600 opacity-100',
        revealOnHover && !copied && 'opacity-0 group-hover:opacity-100 focus-visible:opacity-100'
      )}
    >
      {copied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
    </button>
  );
}
