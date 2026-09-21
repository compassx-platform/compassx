// @ts-nocheck
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import ComputeResourceDetail from '@/modules/compute/components/ComputeResourceDetail';
import { computeApi } from '@/modules/compute/computeApi';
import { useScopedNavigate } from '@/lib/appNavigation';
import { getPrincipalInfo } from '@/lib/auth';
import './compute-page.css';

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
      const data = await computeApi.getResourceStatus(resourceId);
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
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: '13px',
          marginBottom: '16px',
        }}>
          <button
            type="button"
            onClick={() => navigate('/compute')}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: 'var(--color-primary, #6366f1)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '13px',
            }}
          >
            Compute
          </button>
          <span style={{ color: 'var(--color-text-muted)', opacity: 0.5 }}>/</span>
          <span style={{ color: 'var(--color-text-muted)', fontSize: '13px' }}>
            Resource Details
          </span>
        </div>
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
      onRefresh={fetchResource}
    />
  );
}
