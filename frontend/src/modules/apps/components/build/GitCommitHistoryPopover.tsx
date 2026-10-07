import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  GitCommit,
  GitBranch,
  RotateCw,
  Search,
  Copy,
  Check,
  X,
  Clock,
  User,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { useGitCommits, type GitCommitItem } from '../../hooks/useApps';

export interface GitCommitHistoryPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  appId?: string;
  workspaceId?: string;
  workspaceName?: string;
  disabled?: boolean;
}

export function GitCommitHistoryPopover({
  isOpen,
  onClose,
  appId,
  workspaceId,
  workspaceName,
  disabled = false,
}: GitCommitHistoryPopoverProps) {
  const [search, setSearch] = useState('');
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const {
    data: gitData,
    isLoading,
    isFetching,
    refetch,
    error,
  } = useGitCommits(appId, workspaceId, workspaceName, isOpen && !disabled);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  const handleCopy = (hash: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => {
      setCopiedHash((curr) => (curr === hash ? null : curr));
    }, 2000);
  };

  const commits: GitCommitItem[] = gitData?.commits || [];
  const branch = gitData?.branch || 'main';
  const isGit = gitData?.is_git ?? true;

  const filteredCommits = useMemo(() => {
    if (!search.trim()) return commits;
    const q = search.toLowerCase().trim();
    return commits.filter(
      (c) =>
        c.message.toLowerCase().includes(q) ||
        c.short_hash.toLowerCase().includes(q) ||
        c.author.toLowerCase().includes(q)
    );
  }, [commits, search]);

  if (!isOpen) return null;

  return (
    <div
      ref={popoverRef}
      style={{
        position: 'absolute',
        top: 'calc(100% + 6px)',
        right: 0,
        zIndex: 1000,
        width: 380,
        maxWidth: '90vw',
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontSize: '0.8rem',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          borderBottom: '1px solid #e2e8f0',
          background: '#f8fafc',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <GitCommit size={16} className="text-sky-600" />
          <span style={{ fontWeight: 600, color: '#0f172a', fontSize: '0.84rem' }}>
            Commit History
          </span>
          {branch && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                padding: '1px 6px',
                borderRadius: 4,
                background: '#e0f2fe',
                color: '#0369a1',
                fontSize: '0.7rem',
                fontWeight: 500,
              }}
            >
              <GitBranch size={11} />
              {branch}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh commit history"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 24,
              height: 24,
              borderRadius: 4,
              border: 'none',
              background: 'transparent',
              color: '#64748b',
              cursor: isFetching ? 'not-allowed' : 'pointer',
              transition: 'background 0.12s ease',
            }}
            onMouseEnter={(e) => {
              if (!isFetching) e.currentTarget.style.background = '#f1f5f9';
            }}
            onMouseLeave={(e) => {
              if (!isFetching) e.currentTarget.style.background = 'transparent';
            }}
          >
            <RotateCw size={13} className={isFetching ? 'animate-spin text-sky-600' : ''} />
          </button>

          <button
            type="button"
            onClick={onClose}
            title="Close"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 24,
              height: 24,
              borderRadius: 4,
              border: 'none',
              background: 'transparent',
              color: '#64748b',
              cursor: 'pointer',
              transition: 'background 0.12s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Search Filter */}
      {commits.length > 0 && (
        <div style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 6,
              padding: '4px 8px',
            }}
          >
            <Search size={13} color="#94a3b8" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by message, hash, or author..."
              style={{
                border: 'none',
                background: 'transparent',
                outline: 'none',
                width: '100%',
                fontSize: '0.76rem',
                color: '#0f172a',
              }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 0 }}
              >
                <X size={12} color="#94a3b8" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Commit Items List */}
      <div
        style={{
          maxHeight: 340,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          padding: '4px 0',
        }}
      >
        {isLoading ? (
          <div
            style={{
              padding: '30px 16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 8,
              color: '#64748b',
            }}
          >
            <Loader2 size={20} className="animate-spin text-sky-600" />
            <span style={{ fontSize: '0.78rem' }}>Loading git commit history...</span>
          </div>
        ) : error ? (
          <div
            style={{
              padding: '24px 16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              color: '#dc2626',
              textAlign: 'center',
            }}
          >
            <AlertCircle size={18} />
            <span style={{ fontSize: '0.78rem', fontWeight: 500 }}>Failed to load commits</span>
            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
              Ensure dev container is running.
            </span>
          </div>
        ) : !isGit ? (
          <div
            style={{
              padding: '24px 16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              color: '#64748b',
              textAlign: 'center',
            }}
          >
            <GitCommit size={20} color="#94a3b8" />
            <span style={{ fontSize: '0.78rem', fontWeight: 500, color: '#334155' }}>
              Not a Git repository
            </span>
            <span style={{ fontSize: '0.72rem' }}>
              Initialize git or link a remote repo to view commits.
            </span>
          </div>
        ) : filteredCommits.length === 0 ? (
          <div
            style={{
              padding: '24px 16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              color: '#64748b',
              textAlign: 'center',
            }}
          >
            <GitCommit size={20} color="#cbd5e1" />
            <span style={{ fontSize: '0.78rem' }}>
              {search ? 'No matching commits found' : 'No commits on this branch yet'}
            </span>
          </div>
        ) : (
          filteredCommits.map((c, index) => {
            const isCopied = copiedHash === c.hash || copiedHash === c.short_hash;
            return (
              <div
                key={c.hash || `${c.short_hash}_${index}`}
                style={{
                  padding: '8px 14px',
                  borderBottom: index < filteredCommits.length - 1 ? '1px solid #f1f5f9' : 'none',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  transition: 'background 0.1s ease',
                  cursor: 'default',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f8fafc';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                {/* Commit Message */}
                <div
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    color: '#0f172a',
                    lineHeight: 1.35,
                    wordBreak: 'break-word',
                  }}
                >
                  {c.message || 'Commit without message'}
                </div>

                {/* Metadata row: Hash Pill + Author + Relative Time */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.7rem',
                    color: '#64748b',
                    marginTop: 2,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {/* Copyable Hash Pill */}
                    <button
                      type="button"
                      onClick={(e) => handleCopy(c.hash, e)}
                      title={`Full SHA: ${c.hash} (Click to copy)`}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                        padding: '1px 5px',
                        borderRadius: 4,
                        border: '1px solid #e2e8f0',
                        background: '#f1f5f9',
                        color: '#0369a1',
                        fontFamily: 'monospace',
                        fontSize: '0.68rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.12s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#e0f2fe';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = '#f1f5f9';
                      }}
                    >
                      {isCopied ? <Check size={10} color="#16a34a" /> : <Copy size={10} />}
                      <span>{c.short_hash}</span>
                    </button>

                    {c.author && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 3,
                          maxWidth: 130,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        <User size={10} color="#94a3b8" />
                        {c.author}
                      </span>
                    )}
                  </div>

                  {c.relative_date && (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                        color: '#94a3b8',
                      }}
                    >
                      <Clock size={10} />
                      {c.relative_date}
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          padding: '6px 14px',
          borderTop: '1px solid #e2e8f0',
          background: '#f8fafc',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.68rem',
          color: '#64748b',
        }}
      >
        <span>
          {commits.length} {commits.length === 1 ? 'commit' : 'commits'}
        </span>
        <span style={{ fontFamily: 'monospace' }}>HEAD on {branch}</span>
      </div>
    </div>
  );
}
