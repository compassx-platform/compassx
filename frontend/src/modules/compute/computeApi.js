/**
 * Compute module API client.
 * All HTTP calls go through the shared axios instance (@/lib/api).
 * All K8s interaction is handled server-side.
 */
import api from '@/lib/api';
import { getToken } from '@/lib/auth';

const BASE_SSE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const computeApi = {
  getProfiles: async (env) => {
    const res = await api.get('/compute/profiles', env ? { params: { env } } : undefined);
    return res.data;
  },

  // The identity a compute call acts as is taken from the bearer token and
  // X-Workspace-Slug header attached by the api interceptor. It used to be
  // passed as a user_id query parameter, which meant the caller chose whose
  // resources to operate on.
  createResource: async ({ name, runtime, profile, description, customImage, extraEnv }) => {
    const res = await api.post('/compute/resources', {
      name,
      runtime,
      profile,
      description: description ?? null,
      custom_image: customImage ?? null,
      extra_env: extraEnv ?? null,
    });
    return res.data;
  },

  listResources: async () => {
    const res = await api.get('/compute/resources');
    return res.data;
  },

  getResourceStatus: async (resourceId) => {
    const res = await api.get(`/compute/resources/${resourceId}`);
    return res.data;
  },

  deleteResource: async (resourceId) => {
    const res = await api.delete(`/compute/resources/${resourceId}`);
    return res.data;
  },

  startResource: async (resourceId) => {
    const res = await api.post(`/compute/resources/${resourceId}/start`);
    return res.data;
  },

  stopResource: async (resourceId) => {
    const res = await api.post(`/compute/resources/${resourceId}/stop`);
    return res.data;
  },

  startResourceKernel: async (resourceId) => {
    const res = await api.post(`/compute/resources/${resourceId}/start-kernel`, {}, {
      timeout: 120000,
    });
    return res.data;
  },

  // EventSource cannot set headers, so the token and workspace ride in the
  // query string. The middleware reads both from there.
  streamResourceLogs: (resourceId, onLine, onError) => {
    const params = new URLSearchParams();
    const token = getToken();
    if (token) params.set('token', token);
    const match = window.location.pathname.match(/^\/w\/([^/]+)/);
    if (match) params.set('workspace', match[1]);
    const es = new EventSource(`${BASE_SSE}/compute/resources/${resourceId}/logs?${params.toString()}`);
    es.onmessage = (e) => onLine(e.data);
    es.onerror = onError;
    return es;
  },

  listServices: async () => {
    const res = await api.get('/compute/services');
    return res.data;
  },

  controlService: async (serviceName, action) => {
    const res = await api.post(`/compute/services/${serviceName}/${action}`);
    return res.data;
  },

  getPortForwardStatus: async () => {
    const res = await api.get('/compute/services/port-forwards/status');
    return res.data;
  },

  recoverPortForwards: async () => {
    const res = await api.post('/compute/services/port-forwards/recover');
    return res.data;
  },
};


