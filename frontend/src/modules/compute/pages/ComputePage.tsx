// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from 'react';
import { Search } from 'lucide-react';
import ComputeResourcesTable from '@/modules/compute/components/ComputeResourcesTable';
import ComputeServicesPanel from '@/modules/compute/components/ComputeServicesPanel';
import CreateResourceModal from '@/modules/compute/components/CreateResourceModal';
import { computeApi } from '@/modules/compute/computeApi';
import { useScopedNavigate } from '@/lib/appNavigation';
import { PageTabs } from '@/components/common/PageTabs';
import { getPrincipalInfo } from '@/lib/auth';
import './compute-page.css';

const POLL_INTERVAL = 10000;
const COMPUTE_TAB_VALUES = ['resources', 'services'] as const;

export default function ComputePage() {
  const navigate = useScopedNavigate();
  const currentUserId = getPrincipalInfo()?.principal_id;

  const [tab, setTab] = useState('resources');
  const [resources, setResources] = useState([]);
  const [services, setServices] = useState([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [runtimeFilter, setRuntimeFilter] = useState('');
  const [k8sWarning, setK8sWarning] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [loadingId, setLoadingId] = useState(null);
  const [serviceLoadingKey, setServiceLoadingKey] = useState(null);
  const [portForwardStatus, setPortForwardStatus] = useState(null);
  const [portForwardLoading, setPortForwardLoading] = useState(null);
  const pollRef = useRef(null);
  const serviceOrderRef = useRef(new Map());

  const stabilizeServiceOrder = useCallback((list) => {
    const order = serviceOrderRef.current;

    list.forEach((service) => {
      if (!order.has(service.id)) {
        order.set(service.id, order.size);
      }
    });

    return [...list].sort((a, b) => {
      const aOrder = order.get(a.id) ?? Number.MAX_SAFE_INTEGER;
      const bOrder = order.get(b.id) ?? Number.MAX_SAFE_INTEGER;
      return aOrder - bOrder;
    });
  }, []);

  useEffect(() => {
    fetch('/api/v1/compute/health')
      .then((r) => r.json())
      .then((data) => {
        if (data.status !== 'ok') {
          setK8sWarning(data.message || 'Kubernetes not connected. Start minikube.');
        }
      })
      .catch(() => {
        setK8sWarning('Kubernetes not connected. Start minikube.');
      });

    computeApi.getProfiles().then(setProfiles).catch(() => {});
  }, []);

  const fetchResources = useCallback(async () => {
    try {

      const list = await computeApi.listResources(currentUserId);
      setResources(list);

    } catch (e) {
      console.error('[ComputePage] poll resources error:', e);
    }
  }, [currentUserId]);

  const fetchServices = useCallback(async () => {
    try {
      const list = await computeApi.listServices();
      setServices(stabilizeServiceOrder(list));
    } catch (e) {
      console.error('[ComputePage] poll services error:', e);
    }
  }, [stabilizeServiceOrder]);

  const fetchPortForwardStatus = useCallback(async () => {
    try {
      const status = await computeApi.getPortForwardStatus();
      setPortForwardStatus(status);
    } catch (e) {
      console.error('[ComputePage] port-forward status error:', e);
    }
  }, []);

  useEffect(() => {
    fetchResources();
    fetchServices();
    fetchPortForwardStatus();
    pollRef.current = setInterval(() => {
      fetchResources();
      fetchServices();
      fetchPortForwardStatus();
    }, POLL_INTERVAL);
    return () => clearInterval(pollRef.current);
  }, [fetchResources, fetchServices, fetchPortForwardStatus]);

  const handleCreateResource = useCallback(async (data) => {
    try {
      setLoadingId('creating');
      await computeApi.createResource(data, currentUserId, 'current-user');
      await fetchResources();
      setShowCreateModal(false);
    } finally {
      setLoadingId(null);
    }
  }, [fetchResources, currentUserId]);

  const handleStartResource = useCallback(async (resourceId) => {
    try {
      setLoadingId(resourceId);
      await computeApi.startResource(resourceId, currentUserId);
      await fetchResources();
    } catch (e) {
      console.error('[ComputePage] start resource error:', e);
    } finally {
      setLoadingId(null);
    }
  }, [fetchResources, currentUserId]);

  const handleStopResource = useCallback(async (resourceId) => {
    try {
      setLoadingId(resourceId);
      await computeApi.stopResource(resourceId, currentUserId);
      await fetchResources();
    } catch (e) {
      console.error('[ComputePage] stop resource error:', e);
    } finally {
      setLoadingId(null);
    }
  }, [fetchResources, currentUserId]);

  const handleDeleteResource = useCallback(async (resourceId) => {
    try {
      setLoadingId(resourceId);
      await computeApi.deleteResource(resourceId, currentUserId);
      await fetchResources();
    } catch (e) {
      console.error('[ComputePage] delete resource error:', e);
    } finally {
      setLoadingId(null);
    }
  }, [fetchResources, currentUserId]);

  const handleServiceAction = useCallback(async (serviceId, action) => {
    const key = `${serviceId}:${action}`;
    try {
      setServiceLoadingKey(key);
      await computeApi.controlService(serviceId, action);
      await fetchServices();
    } catch (e) {
      console.error('[ComputePage] service action error:', e);
    } finally {
      setServiceLoadingKey(null);
    }
  }, [fetchServices]);

  const handleCheckPortForwards = useCallback(async () => {
    try {
      setPortForwardLoading('check');
      await fetchPortForwardStatus();
    } finally {
      setPortForwardLoading(null);
    }
  }, [fetchPortForwardStatus]);

  const handleRecoverPortForwards = useCallback(async () => {
    try {
      setPortForwardLoading('recover');
      const status = await computeApi.recoverPortForwards();
      setPortForwardStatus(status);
      window.setTimeout(fetchPortForwardStatus, 1200);
    } catch (e) {
      console.error('[ComputePage] port-forward recover error:', e);
    } finally {
      setPortForwardLoading(null);
    }
  }, [fetchPortForwardStatus]);

  const computeTabs = [
    { value: COMPUTE_TAB_VALUES[0], label: `All-purpose Compute (${resources.length})` },
    { value: COMPUTE_TAB_VALUES[1], label: `Services (${services.length})` },
  ];

  const runtimeOptions = Array.from(new Set(resources.map((resource) => resource.runtime).filter(Boolean)));
  const statusOptions = Array.from(new Set(resources.map((resource) => resource.phase).filter(Boolean)));
  const filteredResources = resources.filter((resource) => {
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || [resource.name, resource.profile, resource.runtime, resource.created_by]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
    const matchesStatus = !statusFilter || resource.phase === statusFilter;
    const matchesRuntime = !runtimeFilter || resource.runtime === runtimeFilter;
    return matchesSearch && matchesStatus && matchesRuntime;
  });
  const filteredServices = services.filter((service) => {
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return [service.label, service.id, service.phase, service.message]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });

  return (
    <div className="compute-page">
      <h1 className="compute-title">Compute</h1>

      <PageTabs tabs={computeTabs} value={tab} onChange={setTab} className="compute-tabs" />

      {k8sWarning && (
        <div className="compute-warning">
          {k8sWarning}
        </div>
      )}

      <div className="compute-toolbar">
        <div className="compute-search">
          <Search size={14} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={tab === 'resources' ? 'Filter compute resources' : 'Filter services'}
          />
        </div>
        {tab === 'resources' && (
          <>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">Status</option>
              {statusOptions.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
            <select value={runtimeFilter} onChange={(event) => setRuntimeFilter(event.target.value)}>
              <option value="">Runtime</option>
              {runtimeOptions.map((runtime) => <option key={runtime} value={runtime}>{runtime}</option>)}
            </select>
          </>
        )}
        <div className="compute-toolbar-spacer" />
        {tab === 'resources' && (
          <button className="compute-primary-btn" onClick={() => setShowCreateModal(true)}>
            Create Compute
          </button>
        )}
      </div>

      {tab === 'resources' && (
        <section className="compute-content">
          <ComputeResourcesTable
            resources={filteredResources}
            onStart={handleStartResource}
            onStop={handleStopResource}
            onDelete={handleDeleteResource}
            onSelect={(resource) => navigate(`/compute/${resource.id}`)}
            loadingId={loadingId}
          />
        </section>
      )}

      {tab === 'services' && (
        <section className="compute-content">
          <ComputeServicesPanel
            services={filteredServices}
            loadingKey={serviceLoadingKey}
            onAction={handleServiceAction}
            portForwardStatus={portForwardStatus}
            portForwardLoading={portForwardLoading}
            onCheckPortForwards={handleCheckPortForwards}
            onRecoverPortForwards={handleRecoverPortForwards}
          />
        </section>
      )}

      <CreateResourceModal
        isOpen={showCreateModal}
        profiles={profiles}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateResource}
      />
    </div>
  );
}
