import React from 'react';
import { Rocket, CheckCircle2, AlertCircle, Loader2, ExternalLink } from 'lucide-react';
import type { DeploymentItem } from '../../hooks/useApps';

interface DeploymentStatusCardProps {
  deployment?: DeploymentItem;
  isDeploying?: boolean;
  onViewDetails?: () => void;
}

function timeAgo(dateString: string): string {
  try {
    const diff = (Date.now() - new Date(dateString).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
  } catch (_) {
    return dateString;
  }
}

export function DeploymentStatusCard({
  deployment,
  isDeploying = false,
  onViewDetails,
}: DeploymentStatusCardProps) {
  if (!deployment && !isDeploying) return null;

  const isBuilding = isDeploying || deployment?.status === 'building' || deployment?.status === 'in_progress' || deployment?.status === 'pending';
  const isSuccess = !isBuilding && (deployment?.status === 'success' || deployment?.status === 'active');
  const isFailed = !isBuilding && deployment?.status === 'failed';

  return (
    <div
      style={{
        margin: '0 0 10px 0',
        padding: '10px 14px',
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)',
        fontSize: '0.78rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: '#0f172a' }}>
          <Rocket size={14} color="#2563eb" />
          <span>Deployment</span>
        </div>
        {onViewDetails && (
          <button
            type="button"
            onClick={onViewDetails}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#2563eb',
              cursor: 'pointer',
              fontSize: '0.74rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              fontWeight: 500,
              padding: 0,
            }}
          >
            <span>View details</span>
            <ExternalLink size={11} />
          </button>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {isBuilding ? (
          <>
            <Loader2 size={14} className="animate-spin text-blue-600" />
            <span style={{ color: '#2563eb', fontWeight: 500 }}>
              Deployment in progress...
            </span>
          </>
        ) : isSuccess ? (
          <>
            <CheckCircle2 size={14} color="#16a34a" />
            <span style={{ color: '#64748b' }}>
              Last deploy completed {deployment?.created_at ? timeAgo(deployment.created_at) : 'recently'}
            </span>
          </>
        ) : isFailed ? (
          <>
            <AlertCircle size={14} color="#dc2626" />
            <span style={{ color: '#dc2626' }}>Deployment failed</span>
          </>
        ) : null}

        {deployment?.commit_sha && (
          <span
            style={{
              fontFamily: 'monospace',
              fontSize: '0.72rem',
              background: '#f1f5f9',
              padding: '1px 6px',
              borderRadius: 4,
              color: '#475569',
              marginLeft: 'auto',
            }}
            title={deployment.commit_sha}
          >
            {deployment.commit_sha.slice(0, 7)}
          </span>
        )}
      </div>
    </div>
  );
}
