/**
 * Compute module API client.
 * All HTTP calls go through the shared axios instance (@/lib/api).
 * All K8s interaction is handled server-side.
 */
import api from '@/lib/api';

const BASE_SSE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const computeApi = {
  getProfiles: async (env) => {
    const res = await api.get('/compute/profiles', env ? { params: { env } } : undefined);
    return res.data;
  },

  createResource: async ({ name, runtime, profile, description, customImage, extraEnv }, userId, createdBy) => {
    const res = await api.post('/compute/resources', {
      name,
      runtime,
      profile,
      description: description ?? null,
      custom_image: customImage ?? null,
      extra_env: extraEnv ?? null,
    }, {
      params: { user_id: userId, created_by: createdBy },
    });
    return res.data;
  },

  listResources: async (userId) => {
    const res = await api.get('/compute/resources', { params: { user_id: userId } });
    return res.data;
  },

  getResourceStatus: async (resourceId, userId) => {
    const res = await api.get(`/compute/resources/${resourceId}`, {
      params: { user_id: userId },
    });
    return res.data;
  },

  deleteResource: async (resourceId, userId) => {
    const res = await api.delete(`/compute/resources/${resourceId}`, {
      params: { user_id: userId },
    });
    return res.data;
  },

  startResource: async (resourceId, userId) => {
    const res = await api.post(`/compute/resources/${resourceId}/start`, {}, {
      params: { user_id: userId },
    });
    return res.data;
  },

  stopResource: async (resourceId, userId) => {
    const res = await api.post(`/compute/resources/${resourceId}/stop`, {}, {
      params: { user_id: userId },
    });
    return res.data;
  },

  startResourceKernel: async (resourceId, userId) => {
    const res = await api.post(`/compute/resources/${resourceId}/start-kernel`, {}, {
      params: { user_id: userId },
      timeout: 120000,
    });
    return res.data;
  },

  streamResourceLogs: (resourceId, userId, onLine, onError) => {
    const params = new URLSearchParams({ user_id: userId });
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


