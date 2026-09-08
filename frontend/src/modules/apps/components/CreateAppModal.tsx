import React, { useState, useEffect } from 'react';
import {
  X,
  ChevronRight,
  ChevronLeft,
  GitBranch,
  FolderGit2,
  Boxes,
  FileCode,
  Layers,
  Sparkles,
  Check,
  Globe,
  Code2,
  Info,
  ExternalLink,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
} from 'lucide-react';
import { useGitConnections } from '@/modules/agents/hooks/useGitConnections';

export interface AppCreatePayload {
  name: string;
  description?: string;
  type: string;
  route: string;
  gitProvider: string;
  gitRepoUrl: string;
  gitRef: string;
  gitRefType: string;
  gitSubdir?: string;
  entrypoint?: string;
  gitCredentialType: 'link_account' | 'pat' | 'none';
  gitCredentialNickname?: string;
  gitConnectionId?: number | null;
  gitPat?: string;
}

interface CreateAppModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (appData: AppCreatePayload) => void;
}

export const APP_TYPES = [
  { value: 'custom_web', label: 'Web Application (React / Vite)', icon: Globe },
  { value: 'streamlit', label: 'Streamlit App (Python)', icon: Code2 },
  { value: 'agentic_workflow', label: 'Agentic Workflow App', icon: Layers },
  { value: 'dashboard_app', label: 'Interactive Dashboard', icon: Boxes },
];

const GIT_PROVIDERS = [
  { value: 'github', label: 'GitHub' },
  { value: 'gitlab', label: 'GitLab' },
  { value: 'bitbucket', label: 'Bitbucket' },
  { value: 'azure_devops', label: 'Azure DevOps' },
  { value: 'aws_codecommit', label: 'AWS CodeCommit' },
  { value: 'other', label: 'Other' },
];

const REFERENCE_TYPES = [
  { value: 'branch', label: 'Branch' },
  { value: 'tag', label: 'Tag' },
  { value: 'commit', label: 'Commit' },
];

export function CreateAppModal({ isOpen, onClose, onSubmit }: CreateAppModalProps) {
  const { data: gitConnections = [] } = useGitConnections();

  const [step, setStep] = useState<1 | 2>(1);

  // Step 1: App Info
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [appType, setAppType] = useState('streamlit');
  const [routeSlug, setRouteSlug] = useState('');

  // Step 2: Configure Git Repository (matching design spec)
  const [gitRepoUrl, setGitRepoUrl] = useState('');
  const [gitProvider, setGitProvider] = useState('github');
  const [gitRef, setGitRef] = useState('main');
  const [gitRefType, setGitRefType] = useState('branch');
  const [gitSubdir, setGitSubdir] = useState('');
  const [entrypoint, setEntrypoint] = useState('app.py');

  // Git Credential State
  const [selectedCredentialAction, setSelectedCredentialAction] = useState<string>('new');
  const [credentialType, setCredentialType] = useState<'link_account' | 'pat'>('link_account');
  const [nickname, setNickname] = useState('');
  const [isLinked, setIsLinked] = useState(false);
  const [patToken, setPatToken] = useState('');
  const [showPat, setShowPat] = useState(false);

  // Validation
  const [urlTouched, setUrlTouched] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      const now = new Date();
      const dateStr = now.toISOString().slice(0, 10);
      const timeStr = now.toTimeString().slice(0, 8);
      setNickname(`GitHub ${dateStr} ${timeStr}`);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const isUrlValid =
    !gitRepoUrl.trim() ||
    gitRepoUrl.trim().startsWith('https://') ||
    gitRepoUrl.trim().startsWith('http://') ||
    gitRepoUrl.trim().startsWith('git@');

  function handleNameChange(val: string) {
    setName(val);
    const slug = val
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    setRouteSlug(slug);
    setFormError(null);
  }

  function handleNextStep(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setFormError('App name is required.');
      return;
    }
    setFormError(null);
    setStep(2);
  }

  function handleLinkAccountClick() {
    setIsLinked(true);
  }

  function handleFinalSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault();

    if (!name.trim()) {
      setStep(1);
      setFormError('Please enter an app name.');
      return;
    }

    if (!gitRepoUrl.trim()) {
      setUrlTouched(true);
      setFormError('Git repository URL is required.');
      return;
    }

    if (!isUrlValid) {
      setUrlTouched(true);
      setFormError('Git repository URL must start with https://');
      return;
    }

    const payload: AppCreatePayload = {
      name: name.trim(),
      description: description.trim() || undefined,
      type: APP_TYPES.find((t) => t.value === appType)?.label || appType,
      route: routeSlug.trim()
        ? `/${routeSlug.trim()}`
        : `/${name.trim().toLowerCase().replace(/\s+/g, '-')}`,
      gitProvider,
      gitRepoUrl: gitRepoUrl.trim(),
      gitRef: gitRef.trim() || 'main',
      gitRefType,
      gitSubdir: gitSubdir.trim() || undefined,
      entrypoint: entrypoint.trim() || undefined,
      gitCredentialType: selectedCredentialAction ? credentialType : 'none',
      gitCredentialNickname: nickname.trim() || undefined,
      gitPat: credentialType === 'pat' && patToken.trim() ? patToken.trim() : undefined,
    };

    onSubmit(payload);
  }

  return (
    <div className="uc-modal-overlay" onClick={onClose}>
      <div
        className="uc-modal"
        style={{ maxWidth: 640, width: '100%', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="uc-modal-header" style={{ padding: '16px 24px 12px', borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
              {step === 1 ? 'Add New App' : 'Configure Git repository'}
            </h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
              {step === 1
                ? 'Provide application name and general runtime settings.'
                : 'Optionally configure a Git repository for your app. You can deploy from this repository later.'}
            </p>
          </div>
          <button className="uc-icon-btn" onClick={onClose} title="Close">
            <X size={16} />
          </button>
        </div>

        {/* Step Progress Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '10px 24px',
            background: 'var(--color-surface-hover, #f9fafb)',
            borderBottom: '1px solid var(--color-border)',
            gap: 12,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              opacity: step === 1 ? 1 : 0.8,
            }}
            onClick={() => setStep(1)}
          >
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: '50%',
                background: step === 1 ? 'var(--color-primary)' : 'var(--color-success, #22c55e)',
                color: '#fff',
                fontSize: 11,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {step > 1 ? <Check size={13} /> : '1'}
            </div>
            <span
              style={{
                fontSize: '0.82rem',
                fontWeight: step === 1 ? 600 : 500,
                color: step === 1 ? 'var(--color-primary)' : 'var(--color-text)',
              }}
            >
              App Info
            </span>
          </div>

          <ChevronRight size={14} color="var(--color-text-muted)" />

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              opacity: step === 2 ? 1 : 0.5,
            }}
          >
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: '50%',
                background: step === 2 ? 'var(--color-primary)' : 'var(--color-border)',
                color: step === 2 ? '#fff' : 'var(--color-text-muted)',
                fontSize: 11,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              2
            </div>
            <span
              style={{
                fontSize: '0.82rem',
                fontWeight: step === 2 ? 600 : 500,
                color: step === 2 ? 'var(--color-primary)' : 'var(--color-text-muted)',
              }}
            >
              Git Repository
            </span>
          </div>
        </div>

        {/* Modal Body */}
        <div className="uc-modal-body" style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {formError && (
            <div
              style={{
                marginBottom: 16,
                padding: '8px 12px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: 6,
                color: '#b91c1c',
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <AlertCircle size={15} />
              <span>{formError}</span>
            </div>
          )}

          {/* STEP 1 */}
          {step === 1 && (
            <form id="step-1-form" onSubmit={handleNextStep} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <label className="uc-field">
                <span className="uc-field-label">
                  App Name <span style={{ color: '#ef4444' }}>*</span>
                </span>
                <input
                  autoFocus
                  type="text"
                  placeholder="e.g. Sales Forecast Explorer"
                  value={name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  className="input-field"
                  required
                />
              </label>

              <label className="uc-field">
                <span className="uc-field-label">App Type / Framework</span>
                <select
                  className="input-field"
                  value={appType}
                  onChange={(e) => setAppType(e.target.value)}
                >
                  {APP_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Route / URL Slug</span>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius)',
                    overflow: 'hidden',
                  }}
                >
                  <span
                    style={{
                      padding: '0 10px',
                      fontSize: '0.82rem',
                      color: 'var(--color-text-muted)',
                      background: 'var(--color-surface-hover)',
                      borderRight: '1px solid var(--color-border)',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      userSelect: 'none',
                    }}
                  >
                    /
                  </span>
                  <input
                    type="text"
                    placeholder="sales-forecast-explorer"
                    value={routeSlug}
                    onChange={(e) => setRouteSlug(e.target.value)}
                    style={{
                      border: 'none',
                      outline: 'none',
                      padding: '0.4375rem 0.75rem',
                      flex: 1,
                      fontSize: '0.8125rem',
                      background: 'transparent',
                      color: 'var(--color-text)',
                    }}
                  />
                </div>
              </label>

              <label className="uc-field">
                <span className="uc-field-label">Description</span>
                <textarea
                  placeholder="Briefly describe what this app does..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="input-field"
                  rows={3}
                />
              </label>
            </form>
          )}

          {/* STEP 2: Configure Git repository (Matches Screenshot) */}
          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Row 1: Git repository URL & Git provider */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
                <div>
                  <label className="uc-field" style={{ marginBottom: 0 }}>
                    <span className="uc-field-label">
                      Git repository URL <span style={{ color: '#ef4444' }}>*</span>
                    </span>
                    <input
                      autoFocus
                      type="text"
                      placeholder="https://github.com/organization/repo.git"
                      value={gitRepoUrl}
                      onChange={(e) => {
                        setGitRepoUrl(e.target.value);
                        setUrlTouched(true);
                        setFormError(null);
                      }}
                      onBlur={() => setUrlTouched(true)}
                      className="input-field"
                      style={{
                        borderColor: urlTouched && (!gitRepoUrl.trim() || !isUrlValid) ? '#ef4444' : undefined,
                      }}
                      required
                    />
                  </label>
                  {urlTouched && !isUrlValid && (
                    <div
                      style={{
                        color: '#ef4444',
                        fontSize: '0.75rem',
                        marginTop: 4,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <AlertCircle size={12} />
                      <span>Git repository URL must start with https://</span>
                    </div>
                  )}
                </div>

                <label className="uc-field" style={{ marginBottom: 0 }}>
                  <span className="uc-field-label">Git provider</span>
                  <select
                    className="input-field"
                    value={gitProvider}
                    onChange={(e) => {
                      setGitProvider(e.target.value);
                      const now = new Date();
                      const dateStr = now.toISOString().slice(0, 10);
                      const timeStr = now.toTimeString().slice(0, 8);
                      const pLabel = GIT_PROVIDERS.find((p) => p.value === e.target.value)?.label || 'Git';
                      setNickname(`${pLabel} ${dateStr} ${timeStr}`);
                    }}
                  >
                    {GIT_PROVIDERS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {/* Row 2: Git reference & Reference type */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
                <label className="uc-field" style={{ marginBottom: 0 }}>
                  <span className="uc-field-label">Git reference (branch/tag/commit)</span>
                  <input
                    type="text"
                    placeholder="main"
                    value={gitRef}
                    onChange={(e) => setGitRef(e.target.value)}
                    className="input-field"
                  />
                </label>

                <label className="uc-field" style={{ marginBottom: 0 }}>
                  <span className="uc-field-label">Reference type</span>
                  <select
                    className="input-field"
                    value={gitRefType}
                    onChange={(e) => setGitRefType(e.target.value)}
                  >
                    {REFERENCE_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {/* Row 3: Source code path */}
              <label className="uc-field">
                <span className="uc-field-label">Source code path</span>
                <input
                  type="text"
                  placeholder="Enter the source code folder path, or leave empty if the repo includes the entire project."
                  value={gitSubdir}
                  onChange={(e) => setGitSubdir(e.target.value)}
                  className="input-field"
                />
              </label>

              {/* Row 4: Git credential (optional) */}
              <label className="uc-field" style={{ marginBottom: 4 }}>
                <span className="uc-field-label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span>Git credential (optional)</span>
                  <Info size={13} color="var(--color-text-muted)" />
                </span>
                <select
                  className="input-field"
                  value={selectedCredentialAction}
                  onChange={(e) => setSelectedCredentialAction(e.target.value)}
                >
                  <option value="new">+ Add Git credential</option>
                  {gitConnections.map((c) => (
                    <option key={c.id} value={`conn_${c.id}`}>
                      {c.name} ({c.provider})
                    </option>
                  ))}
                  <option value="">None (Public Repository)</option>
                </select>
              </label>

              {/* Credential Options Card Section */}
              {selectedCredentialAction === 'new' && (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 14,
                    padding: '14px 16px',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 8,
                  }}
                >
                  {/* Nickname field */}
                  <label className="uc-field" style={{ marginBottom: 0 }}>
                    <span className="uc-field-label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span>Nickname</span>
                      <Info size={13} color="var(--color-text-muted)" />
                    </span>
                    <input
                      type="text"
                      value={nickname}
                      onChange={(e) => setNickname(e.target.value)}
                      className="input-field"
                      placeholder="e.g. GitHub 2026-09-06"
                    />
                  </label>

                  {/* 2 Options Side-by-Side */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    {/* Option 1: Link Git account */}
                    <div
                      onClick={() => setCredentialType('link_account')}
                      style={{
                        padding: '12px 14px',
                        borderRadius: 8,
                        border: credentialType === 'link_account'
                          ? '1.5px solid var(--color-primary, #1B6EF3)'
                          : '1px solid var(--color-border)',
                        background: credentialType === 'link_account'
                          ? 'var(--color-primary-bg, #EBF2FF)'
                          : 'var(--color-surface)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <input
                          type="radio"
                          name="git_credential_option"
                          checked={credentialType === 'link_account'}
                          onChange={() => setCredentialType('link_account')}
                          style={{ accentColor: 'var(--color-primary)', cursor: 'pointer' }}
                        />
                        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--color-text)' }}>
                          Link Git account
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: 1.4, paddingLeft: 22 }}>
                        Simple setup in a few clicks to link your GitHub account.{' '}
                        <span
                          style={{
                            color: 'var(--color-primary)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 2,
                            fontWeight: 500,
                          }}
                        >
                          Learn more <ExternalLink size={10} />
                        </span>
                      </p>
                    </div>

                    {/* Option 2: Personal access token */}
                    <div
                      onClick={() => setCredentialType('pat')}
                      style={{
                        padding: '12px 14px',
                        borderRadius: 8,
                        border: credentialType === 'pat'
                          ? '1.5px solid var(--color-primary, #1B6EF3)'
                          : '1px solid var(--color-border)',
                        background: credentialType === 'pat'
                          ? 'var(--color-primary-bg, #EBF2FF)'
                          : 'var(--color-surface)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <input
                          type="radio"
                          name="git_credential_option"
                          checked={credentialType === 'pat'}
                          onChange={() => setCredentialType('pat')}
                          style={{ accentColor: 'var(--color-primary)', cursor: 'pointer' }}
                        />
                        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--color-text)' }}>
                          Personal access token
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: 1.4, paddingLeft: 22 }}>
                        Use an existing personal access token to authenticate Git requests.
                      </p>
                    </div>
                  </div>

                  {/* Context Actions based on chosen option */}
                  {credentialType === 'link_account' ? (
                    <div>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={handleLinkAccountClick}
                        style={{ padding: '6px 16px', fontSize: '0.82rem' }}
                      >
                        {isLinked ? (
                          <>
                            <Check size={14} /> Linked
                          </>
                        ) : (
                          'Link'
                        )}
                      </button>
                    </div>
                  ) : (
                    <div style={{ marginTop: 4 }}>
                      <label className="uc-field" style={{ marginBottom: 0 }}>
                        <span className="uc-field-label">Personal Access Token (PAT)</span>
                        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                          <Lock size={13} color="var(--color-text-muted)" style={{ position: 'absolute', left: 10 }} />
                          <input
                            type={showPat ? 'text' : 'password'}
                            placeholder="ghp_••••••••••••••••••••••••"
                            value={patToken}
                            onChange={(e) => setPatToken(e.target.value)}
                            className="input-field"
                            style={{ paddingLeft: 30, paddingRight: 32 }}
                          />
                          <button
                            type="button"
                            onClick={() => setShowPat((v) => !v)}
                            style={{
                              position: 'absolute',
                              right: 8,
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              color: 'var(--color-text-muted)',
                              padding: 0,
                            }}
                          >
                            {showPat ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        </div>
                      </label>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div
          className="uc-modal-footer"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '14px 24px',
            borderTop: '1px solid var(--color-border)',
            background: 'var(--color-surface)',
          }}
        >
          {step === 1 ? (
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button
                type="submit"
                form="step-1-form"
                className="btn btn-primary"
                disabled={!name.trim()}
              >
                <span>Next: Configure Git</span>
                <ChevronRight size={14} />
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                className="btn btn-outline"
                style={{ border: 'none', background: 'transparent', padding: '6px 0', color: 'var(--color-primary)' }}
                onClick={() => {
                  setFormError(null);
                  setStep(1);
                }}
              >
                Back
              </button>

              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => handleFinalSubmit()}
                >
                  Next: Configure
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => handleFinalSubmit()}
                >
                  Create app
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
