import React, { useState, useRef, useEffect } from 'react';
import {
  Monitor,
  Tablet,
  Smartphone,
  RotateCw,
  ExternalLink,
  Copy,
  Check,
  Play,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Globe,
  Radio,
  Maximize2,
  RefreshCw,
} from 'lucide-react';
import { AppItem, DevSessionStatus } from '../../hooks/useApps';
import { useToast } from '@/lib/toast';

interface AppPreviewPanelProps {
  app: AppItem;
  resolvedAppId: string;
  devStatus?: DevSessionStatus;
  isDevPodRunning: boolean;
  isDevPodStarting: boolean;
  onStartDevPod: () => Promise<void>;
  onRefreshTriggered?: () => void;
  externalRefreshKey?: number;
}

type ViewportMode = 'desktop' | 'tablet' | 'mobile';

const VIEWPORT_WIDTHS: Record<ViewportMode, string> = {
  desktop: '100%',
  tablet: '768px',
  mobile: '375px',
};

export function AppPreviewPanel({
  app,
  resolvedAppId,
  devStatus,
  isDevPodRunning,
  isDevPodStarting,
  onStartDevPod,
  onRefreshTriggered,
  externalRefreshKey = 0,
}: AppPreviewPanelProps) {
  const toast = useToast();
  const [viewport, setViewport] = useState<ViewportMode>('desktop');
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [isIframeLoading, setIsIframeLoading] = useState(true);
  const [reloadCounter, setReloadCounter] = useState(0);
  const [iframeError, setIframeError] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const liveDevUrl =
    devStatus?.dev_url || `https://${app.slug}-dev.135.13.180.167.nip.io`;

  // Construct cache-busted URL when user clicks reload or AI triggers auto-refresh
  const previewUrlWithCacheBust = `${liveDevUrl}${liveDevUrl.includes('?') ? '&' : '?'}_t=${Date.now()}_${reloadCounter}_${externalRefreshKey}`;

  // When external refresh key changes (e.g. AI finished editing files), trigger iframe reload
  useEffect(() => {
    if (externalRefreshKey > 0) {
      handleReload();
    }
  }, [externalRefreshKey]);

  function handleReload() {
    setIsIframeLoading(true);
    setIframeError(false);
    setReloadCounter((prev) => prev + 1);
    if (iframeRef.current) {
      try {
        iframeRef.current.src = `${liveDevUrl}${liveDevUrl.includes('?') ? '&' : '?'}_t=${Date.now()}`;
      } catch (e) {
        // cross-origin reload
      }
    }
    if (onRefreshTriggered) {
      onRefreshTriggered();
    }
  }

  function handleCopyUrl() {
    navigator.clipboard.writeText(liveDevUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
    toast.success('Live preview URL copied to clipboard');
  }

  function handleOpenExternal() {
    window.open(liveDevUrl, '_blank', 'noopener,noreferrer');
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        background: '#0f172a',
        borderRight: '1px solid var(--color-border)',
        overflow: 'hidden',
      }}
    >
      {/* Top Controls Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          background: '#1e293b',
          borderBottom: '1px solid #334155',
          gap: 12,
          flexWrap: 'wrap',
          minHeight: 48,
        }}
      >
        {/* Left: Viewport Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#0f172a', padding: '3px', borderRadius: 8 }}>
          <button
            onClick={() => setViewport('desktop')}
            title="Desktop View (100%)"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 8px',
              borderRadius: 6,
              border: 'none',
              background: viewport === 'desktop' ? '#3b82f6' : 'transparent',
              color: viewport === 'desktop' ? '#ffffff' : '#94a3b8',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Monitor size={14} />
            <span>Desktop</span>
          </button>

          <button
            onClick={() => setViewport('tablet')}
            title="Tablet View (768px)"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 8px',
              borderRadius: 6,
              border: 'none',
              background: viewport === 'tablet' ? '#3b82f6' : 'transparent',
              color: viewport === 'tablet' ? '#ffffff' : '#94a3b8',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Tablet size={14} />
            <span>Tablet</span>
          </button>

          <button
            onClick={() => setViewport('mobile')}
            title="Mobile View (375px)"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 8px',
              borderRadius: 6,
              border: 'none',
              background: viewport === 'mobile' ? '#3b82f6' : 'transparent',
              color: viewport === 'mobile' ? '#ffffff' : '#94a3b8',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Smartphone size={14} />
            <span>Mobile</span>
          </button>
        </div>

        {/* Center: Live URL Bar */}
        <div
          style={{
            flex: 1,
            maxWidth: 420,
            minWidth: 200,
            display: 'flex',
            alignItems: 'center',
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 6,
            padding: '4px 10px',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {isDevPodRunning ? (
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: '#22c55e',
                  boxShadow: '0 0 6px #22c55e',
                }}
                title="Live Sandbox Pod Active"
              />
            ) : isDevPodStarting ? (
              <Loader2 size={12} className="spin" color="#38bdf8" />
            ) : (
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#ef4444' }} title="Dev Pod Stopped" />
            )}
            <Globe size={13} color="#64748b" />
          </div>

          <span
            style={{
              flex: 1,
              fontSize: '0.76rem',
              color: '#e2e8f0',
              fontFamily: 'monospace',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={liveDevUrl}
          >
            {liveDevUrl.replace(/^https?:\/\//, '')}
          </span>

          <button
            onClick={handleCopyUrl}
            title="Copy Dev Sandbox URL"
            style={{
              background: 'none',
              border: 'none',
              color: copiedUrl ? '#22c55e' : '#94a3b8',
              cursor: 'pointer',
              padding: 2,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {copiedUrl ? <Check size={13} /> : <Copy size={13} />}
          </button>

          <button
            onClick={handleOpenExternal}
            title="Open Live App in Dedicated Tab"
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: 2,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <ExternalLink size={13} />
          </button>
        </div>

        {/* Right: Refresh & Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={handleReload}
            disabled={!isDevPodRunning}
            title="Refresh Live Preview"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 10px',
              borderRadius: 6,
              background: '#334155',
              border: 'none',
              color: '#f8fafc',
              fontSize: '0.75rem',
              fontWeight: 500,
              cursor: isDevPodRunning ? 'pointer' : 'not-allowed',
              opacity: isDevPodRunning ? 1 : 0.6,
              transition: 'background 0.15s ease',
            }}
          >
            <RotateCw size={13} className={isIframeLoading ? 'spin' : ''} />
            <span>Reload</span>
          </button>

          {!isDevPodRunning && (
            <button
              onClick={onStartDevPod}
              disabled={isDevPodStarting}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 12px',
                borderRadius: 6,
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                border: 'none',
                color: '#ffffff',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: isDevPodStarting ? 'not-allowed' : 'pointer',
                boxShadow: '0 2px 6px rgba(16, 185, 129, 0.3)',
              }}
            >
              {isDevPodStarting ? <Loader2 size={13} className="spin" /> : <Play size={12} fill="#fff" />}
              <span>{isDevPodStarting ? 'Starting Pod...' : 'Start Dev Pod'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Iframe Canvas Area */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#090d16',
          padding: viewport === 'desktop' ? 0 : '16px 20px',
          overflow: 'auto',
          position: 'relative',
        }}
      >
        {isDevPodRunning ? (
          <div
            style={{
              width: VIEWPORT_WIDTHS[viewport],
              height: '100%',
              maxHeight: viewport === 'desktop' ? '100%' : 'calc(100% - 10px)',
              background: '#ffffff',
              borderRadius: viewport === 'desktop' ? 0 : 12,
              boxShadow: viewport === 'desktop' ? 'none' : '0 12px 36px rgba(0, 0, 0, 0.5), 0 0 0 1px #334155',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              position: 'relative',
              transition: 'width 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          >
            {/* Viewport Frame Header (Tablet/Mobile only) */}
            {viewport !== 'desktop' && (
              <div
                style={{
                  height: 28,
                  background: '#1e293b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderBottom: '1px solid #334155',
                  padding: '0 12px',
                  position: 'relative',
                }}
              >
                <div style={{ position: 'absolute', left: 10, display: 'flex', gap: 5 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444' }} />
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b' }} />
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }} />
                </div>
                <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 500 }}>
                  {viewport === 'tablet' ? 'iPad / Tablet (768px)' : 'iPhone / Mobile (375px)'}
                </span>
              </div>
            )}

            {/* Loading Overlay */}
            {isIframeLoading && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'rgba(15, 23, 42, 0.85)',
                  backdropFilter: 'blur(3px)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  zIndex: 10,
                  color: '#f8fafc',
                }}
              >
                <Loader2 size={32} className="spin" color="#38bdf8" />
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>Loading live application preview...</div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 3 }}>
                    Streaming from sandbox pod ({devStatus?.dev_port || 9201})
                  </div>
                </div>
              </div>
            )}

            {/* Interactive Preview Iframe */}
            <iframe
              ref={iframeRef}
              src={previewUrlWithCacheBust}
              title={`Live Preview - ${app.name}`}
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                background: '#ffffff',
              }}
              onLoad={() => {
                setIsIframeLoading(false);
                setIframeError(false);
              }}
              onError={() => {
                setIsIframeLoading(false);
                setIframeError(true);
              }}
            />
          </div>
        ) : isDevPodStarting ? (
          /* Dev Pod Starting Skeleton */
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 16,
              padding: 32,
              textAlign: 'center',
              color: '#f8fafc',
              maxWidth: 420,
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: '50%',
                background: 'rgba(56, 189, 248, 0.15)',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Loader2 size={32} className="spin" color="#38bdf8" />
            </div>

            <div>
              <h3 style={{ margin: '0 0 6px', fontSize: '1.1rem', fontWeight: 600, color: '#ffffff' }}>
                Starting Isolated Dev Pod...
              </h3>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.5 }}>
                Allocating cluster compute, mounting workspace, and establishing Omnigent live pairing tunnel.
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 14px',
                borderRadius: 20,
                background: '#1e293b',
                border: '1px solid #334155',
                fontSize: '0.75rem',
                color: '#38bdf8',
                fontWeight: 600,
              }}
            >
              <Radio size={12} className="spin" />
              <span>Attaching Port {devStatus?.dev_port || 9201}...</span>
            </div>
          </div>
        ) : (
          /* Dev Pod Stopped / Launch Prompt */
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 20,
              padding: 40,
              textAlign: 'center',
              color: '#f8fafc',
              maxWidth: 460,
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 16,
              boxShadow: '0 12px 32px rgba(0, 0, 0, 0.4)',
            }}
          >
            <div
              style={{
                width: 68,
                height: 68,
                borderRadius: 18,
                background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.2) 100%)',
                border: '1px solid rgba(99, 102, 241, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8',
              }}
            >
              <Globe size={34} />
            </div>

            <div>
              <h3 style={{ margin: '0 0 8px', fontSize: '1.15rem', fontWeight: 700, color: '#ffffff' }}>
                Dev Sandbox is Stopped
              </h3>
              <p style={{ margin: 0, fontSize: '0.84rem', color: '#94a3b8', lineHeight: 1.5 }}>
                Start the development sandbox pod to preview <strong style={{ color: '#e2e8f0' }}>{app.name}</strong> live with instant hot-reloading and AI pair programming.
              </p>
            </div>

            <button
              onClick={onStartDevPod}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 22px',
                borderRadius: 8,
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                border: 'none',
                color: '#ffffff',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)',
                transition: 'transform 0.15s ease, box-shadow 0.15s ease',
              }}
            >
              <Play size={16} fill="#ffffff" />
              <span>Launch Live Sandbox</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
