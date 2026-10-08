// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from 'react';
import { Search } from 'lucide-react';
import ComputeResourcesTable from '@/modules/compute/components/ComputeResourcesTable';
import ComputeServicesPanel from '@/modules/compute/components/ComputeServicesPanel';
import ComputeSandboxesTable from '@/modules/compute/components/ComputeSandboxesTable';
import CreateResourceModal from '@/modules/compute/components/CreateResourceModal';
import CreateSandboxModal from '@/modules/compute/components/CreateSandboxModal';
import { computeApi } from '@/modules/compute/computeApi';
import { useScopedNavigate } from '@/lib/appNavigation';
import { PageTabs } from '@/components/common/PageTabs';
import { getPrincipalInfo } from '@/lib/auth';
import './compute-page.css';

const POLL_INTERVAL = 10000;
const COMPUTE_TAB_VALUES = ['resources', 'services', 'sandboxes'] as const;

export default function ComputePage() {
  const navigate = useScopedNavigate();
  const currentUserId = getPrincipalInfo()?.principal_id;

  const [tab, setTab] = useState('resources');
  const [resources, setResources] = useState([]);
  const [services, setServices] = useState([]);
  const [sandboxes, setSandboxes] = useState([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [runtimeFilter, setRuntimeFilter] = useState('');
  const [consumerFilter, setConsumerFilter] = useState('');
  const [k8sWarning, setK8sWarning] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showCreateSandboxModal, setShowCreateSandboxModal] = useState(false);
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
    computeApi.getHealth()
      .then((data) => {
        if (data.status !== 'ok') {
          setK8sWarning(data.message || 'Compute infrastructure not connected.');
        } else {
          setK8sWarning(null);
        }
      })
      .catch((err) => {
        if (err.response?.status === 503 && err.response?.data?.message) {
          setK8sWarning(err.response.data.message);
        }
      });

    computeApi.getProfiles().then(setProfiles).catch(() => {});
  }, []);

  const fetchResources = useCallback(async () => {
    try {
      const list = await computeApi.listResources();
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

  const fetchSandboxes = useCallback(async () => {
    try {
      const list = await computeApi.listSandboxes();
      setSandboxes(list || []);
    } catch (e) {
      console.error('[ComputePage] poll sandboxes error:', e);
    }
  }, []);

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
    fetchSandboxes();
    fetchPortForwardStatus();
    pollRef.current = setInterval(() => {
      fetchResources();
      fetchServices();
      fetchSandboxes();
      fetchPortForwardStatus();
    }, POLL_INTERVAL);
    return () => clearInterval(pollRef.current);
  }, [fetchResources, fetchServices, fetchSandboxes, fetchPortForwardStatus]);

  const handleCreateResource = useCallback(async (data) => {
    try {
      setLoadingId('creating');
      await computeApi.createResource(data);
      await fetchResources();
      setShowCreateModal(false);
    } finally {
      setLoadingId(null);
    }
  }, [fetchResources, currentUserId]);

  const handleStartResource = useCallback(async (resourceId) => {
    try {
      setLoadingId(resourceId);
      await computeApi.startResource(resourceId);
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
      await computeApi.stopResource(resourceId);
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
      await computeApi.deleteResource(resourceId);
      await fetchResources();
    } catch (e) {
      console.error('[ComputePage] delete resource error:', e);
    } finally {
      setLoadingId(null);
    }
  }, [fetchResources, currentUserId]);

  // ── Sandbox Handlers ───────────────────────────────────────────────────────
  const handleProvisionSandbox = useCallback(async (spec) => {
    try {
      setLoadingId('provisioning-sandbox');
      await computeApi.provisionSandbox(spec);
      await fetchSandboxes();
    } finally {
      setLoadingId(null);
    }
  }, [fetchSandboxes]);

  const handleTerminateSandbox = useCallback(async (sandboxId) => {
    try {
      setLoadingId(sandboxId);
      await computeApi.terminateSandbox(sandboxId);
      await fetchSandboxes();
    } catch (e) {
      console.error('[ComputePage] terminate sandbox error:', e);
    } finally {
      setLoadingId(null);
    }
  }, [fetchSandboxes]);

  const handleSuspendSandbox = useCallback(async (sandboxId) => {
    try {
      setLoadingId(sandboxId);
      await computeApi.suspendSandbox(sandboxId);
      await fetchSandboxes();
    } catch (e) {
      console.error('[ComputePage] suspend sandbox error:', e);
    } finally {
      setLoadingId(null);
    }
  }, [fetchSandboxes]);

  const handleResumeSandbox = useCallback(async (sandboxId) => {
    try {
      setLoadingId(sandboxId);
      await computeApi.resumeSandbox(sandboxId);
      await fetchSandboxes();
    } catch (e) {
      console.error('[ComputePage] resume sandbox error:', e);
    } finally {
      setLoadingId(null);
    }
  }, [fetchSandboxes]);

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
    { value: COMPUTE_TAB_VALUES[2], label: `Sandboxes (${sandboxes.length})` },
  ];

  const runtimeOptions = Array.from(new Set(resources.map((resource) => resource.runtime).filter(Boolean)));
  const statusOptions = Array.from(new Set(resources.map((resource) => resource.phase).filter(Boolean)));
  const sandboxStatusOptions = Array.from(new Set(sandboxes.map((sb) => sb.status).filter(Boolean)));
  const consumerOptions = Array.from(new Set(sandboxes.map((sb) => sb.consumer_module).filter(Boolean)));

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

  const filteredSandboxes = sandboxes.filter((sb) => {
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || [sb.name, sb.id, sb.consumer_module, sb.image, sb.runtime_mode]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
    const matchesStatus = !statusFilter || String(sb.status).toLowerCase() === statusFilter.toLowerCase();
    const matchesConsumer = !consumerFilter || String(sb.consumer_module).toLowerCase() === consumerFilter.toLowerCase();
    return matchesSearch && matchesStatus && matchesConsumer;
  });

  return (
    <div className="compute-page">
      <h1 className="compute-title">Compute</h1>

      <PageTabs tabs={computeTabs} value={tab} onChange={(newTab) => {
        setTab(newTab);
        setStatusFilter('');
        setRuntimeFilter('');
        setConsumerFilter('');
      }} className="compute-tabs" />

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
            placeholder={
              tab === 'resources'
                ? 'Filter compute resources'
                : tab === 'sandboxes'
                ? 'Filter sandboxes'
                : 'Filter services'
            }
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

        {tab === 'sandboxes' && (
          <>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All Statuses</option>
              {sandboxStatusOptions.map((st) => <option key={st} value={st}>{st}</option>)}
            </select>
            <select value={consumerFilter} onChange={(event) => setConsumerFilter(event.target.value)}>
              <option value="">All Consumers</option>
              {consumerOptions.map((mod) => <option key={mod} value={mod}>{mod}</option>)}
            </select>
          </>
        )}

        <div className="compute-toolbar-spacer" />

        {tab === 'resources' && (
          <button className="compute-primary-btn" onClick={() => setShowCreateModal(true)}>
            Create Compute
          </button>
        )}

        {tab === 'sandboxes' && (
          <button className="compute-primary-btn" onClick={() => setShowCreateSandboxModal(true)}>
            Provision Sandbox
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

      {tab === 'sandboxes' && (
        <section className="compute-content">
          <ComputeSandboxesTable
            sandboxes={filteredSandboxes}
            onTerminate={handleTerminateSandbox}
            onSuspend={handleSuspendSandbox}
            onResume={handleResumeSandbox}
            loadingId={loadingId}
            onRefresh={fetchSandboxes}
          />
        </section>
      )}

      <CreateResourceModal
        isOpen={showCreateModal}
        profiles={profiles}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateResource}
      />

      <CreateSandboxModal
        isOpen={showCreateSandboxModal}
        onClose={() => setShowCreateSandboxModal(false)}
        onProvision={handleProvisionSandbox}
      />
    </div>
  );
}

