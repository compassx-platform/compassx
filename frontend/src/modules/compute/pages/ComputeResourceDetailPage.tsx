// @ts-nocheck
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import ComputeResourceDetail from '@/modules/compute/components/ComputeResourceDetail';
import { computeApi } from '@/modules/compute/computeApi';
import { useScopedNavigate } from '@/lib/appNavigation';
import { getPrincipalInfo } from '@/lib/auth';

const POLL_INTERVAL = 10000;

export default function ComputeResourceDetailPage() {
  const { resourceId } = useParams();
  const navigate = useScopedNavigate();
  const [resource, setResource] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const pollIntervalRef = { current: null };

  const currentUserId = getPrincipalInfo()?.principal_id;

  const fetchResource = useCallback(async () => {
    if (!resourceId) return;
    try {
      const data = await computeApi.getResourceStatus(resourceId, currentUserId);
      setResource(data);
      setError(null);
    } catch (e) {
      console.error('[ComputeResourceDetailPage] fetch error:', e);
      setError('Failed to load resource');
    } finally {
      setLoading(false);
    }
  }, [resourceId, currentUserId]);

  useEffect(() => {
    fetchResource();
    pollIntervalRef.current = setInterval(fetchResource, POLL_INTERVAL);
    return () => clearInterval(pollIntervalRef.current);
  }, [fetchResource]);

  if (loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Loading resource...
      </div>
    );
  }

  if (error || !resource) {
    return (
      <div style={{ padding: '24px' }}>
        <button
          onClick={() => navigate('/compute')}
          style={{
            padding: '8px 16px',
            background: 'var(--color-accent, #6366f1)',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            marginBottom: '16px',
          }}
        >
          ← Back to Compute
        </button>
        <div style={{ color: 'var(--color-error, #ef4444)' }}>
          {error || 'Resource not found'}
        </div>
      </div>
    );
  }

  return (
    <ComputeResourceDetail
      resource={resource}
      onClose={() => navigate('/compute')}
    />
  );
}
