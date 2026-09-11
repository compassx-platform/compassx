import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

export type TaskStatus = 'backlog' | 'in_progress' | 'testing' | 'waiting_for_deployment' | 'completed';
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface AppTask {
  id: string;
  app_id: string;
  workspace_id: string;
  title: string;
  description?: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  tags?: string[] | null;
  assignee?: string | null;
  due_date?: string | null;
  order: number;
  created_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAppTaskPayload {
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  tags?: string[];
  assignee?: string | null;
  due_date?: string | null;
  order?: number;
}

export interface UpdateAppTaskPayload {
  title?: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  tags?: string[];
  assignee?: string | null;
  due_date?: string | null;
  order?: number;
}

export interface ColumnConfig {
  id: TaskStatus;
  title: string;
  badgeColor: string;
  accentColor: string;
  headerBg: string;
  iconName: string;
}

export const TASK_COLUMNS: ColumnConfig[] = [
  {
    id: 'backlog',
    title: 'Task Backlogs',
    badgeColor: '#64748b',
    accentColor: '#94a3b8',
    headerBg: 'rgba(100, 116, 139, 0.08)',
    iconName: 'ListOrdered',
  },
  {
    id: 'in_progress',
    title: 'In Progress',
    badgeColor: '#3b82f6',
    accentColor: '#60a5fa',
    headerBg: 'rgba(59, 130, 246, 0.08)',
    iconName: 'PlayCircle',
  },
  {
    id: 'testing',
    title: 'Testing',
    badgeColor: '#f59e0b',
    accentColor: '#fbbf24',
    headerBg: 'rgba(245, 158, 11, 0.08)',
    iconName: 'FlaskConical',
  },
  {
    id: 'waiting_for_deployment',
    title: 'Waiting for Deployment',
    badgeColor: '#8b5cf6',
    accentColor: '#a78bfa',
    headerBg: 'rgba(139, 92, 246, 0.08)',
    iconName: 'Rocket',
  },
  {
    id: 'completed',
    title: 'Completed',
    badgeColor: '#10b981',
    accentColor: '#34d399',
    headerBg: 'rgba(16, 185, 129, 0.08)',
    iconName: 'CheckCircle2',
  },
];

export const PRIORITY_CONFIG: Record<
  TaskPriority,
  { label: string; color: string; bg: string; border: string }
> = {
  urgent: {
    label: 'Urgent',
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.12)',
    border: 'rgba(239, 68, 68, 0.3)',
  },
  high: {
    label: 'High',
    color: '#f97316',
    bg: 'rgba(249, 115, 22, 0.12)',
    border: 'rgba(249, 115, 22, 0.3)',
  },
  medium: {
    label: 'Medium',
    color: '#3b82f6',
    bg: 'rgba(59, 130, 246, 0.12)',
    border: 'rgba(59, 130, 246, 0.3)',
  },
  low: {
    label: 'Low',
    color: '#64748b',
    bg: 'rgba(100, 116, 139, 0.12)',
    border: 'rgba(100, 116, 139, 0.3)',
  },
};

export function useAppTasks(appId?: string, enabled = true) {
  return useQuery({
    queryKey: ['app-tasks', appId],
    queryFn: async () => {
      if (!appId) return [];
      const res = await api.get<AppTask[]>(`/apps/${appId}/tasks`);
      return res.data;
    },
    enabled: !!appId && enabled,
    staleTime: 10_000,
  });
}

export function useCreateAppTask() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({ appId, payload }: { appId: string; payload: CreateAppTaskPayload }) => {
      const res = await api.post<AppTask>(`/apps/${appId}/tasks`, payload);
      return res.data;
    },
    onSuccess: (data, { appId }) => {
      qc.setQueryData<AppTask[]>(['app-tasks', appId], (old) => {
        if (!old) return [data];
        return [...old, data];
      });
      qc.invalidateQueries({ queryKey: ['app-tasks', appId] });
    },
  });
}

export function useUpdateAppTask() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({
      appId,
      taskId,
      payload,
    }: {
      appId: string;
      taskId: string;
      payload: UpdateAppTaskPayload;
    }) => {
      const res = await api.put<AppTask>(`/apps/${appId}/tasks/${taskId}`, payload);
      return res.data;
    },
    onSuccess: (data, { appId }) => {
      qc.setQueryData<AppTask[]>(['app-tasks', appId], (old) => {
        if (!old) return [data];
        return old.map((t) => (t.id === data.id ? data : t));
      });
      qc.invalidateQueries({ queryKey: ['app-tasks', appId] });
    },
  });
}

export function useUpdateAppTaskStatus() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({
      appId,
      taskId,
      status,
      order,
    }: {
      appId: string;
      taskId: string;
      status: TaskStatus;
      order?: number;
    }) => {
      const res = await api.patch<AppTask>(`/apps/${appId}/tasks/${taskId}/status`, {
        status,
        order,
      });
      return res.data;
    },
    onMutate: async ({ appId, taskId, status, order }) => {
      await qc.cancelQueries({ queryKey: ['app-tasks', appId] });
      const prevTasks = qc.getQueryData<AppTask[]>(['app-tasks', appId]);
      if (prevTasks) {
        qc.setQueryData<AppTask[]>(
          ['app-tasks', appId],
          prevTasks.map((t) =>
            t.id === taskId ? { ...t, status, ...(order !== undefined ? { order } : {}) } : t
          )
        );
      }
      return { prevTasks };
    },
    onError: (_err, { appId }, context) => {
      if (context?.prevTasks) {
        qc.setQueryData(['app-tasks', appId], context.prevTasks);
      }
    },
    onSettled: (_, __, { appId }) => {
      qc.invalidateQueries({ queryKey: ['app-tasks', appId] });
    },
  });
}

export function useReorderAppTasks() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({
      appId,
      items,
    }: {
      appId: string;
      items: Array<{ task_id: string; status: string; order: number }>;
    }) => {
      const res = await api.post<AppTask[]>(`/apps/${appId}/tasks/reorder`, { items });
      return res.data;
    },
    onSuccess: (_, { appId }) => {
      qc.invalidateQueries({ queryKey: ['app-tasks', appId] });
    },
  });
}

export function useDeleteAppTask() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({ appId, taskId }: { appId: string; taskId: string }) => {
      await api.delete(`/apps/${appId}/tasks/${taskId}`);
    },
    onSuccess: (_, { appId, taskId }) => {
      qc.setQueryData<AppTask[]>(['app-tasks', appId], (old) => {
        if (!old) return [];
        return old.filter((t) => t.id !== taskId);
      });
      qc.invalidateQueries({ queryKey: ['app-tasks', appId] });
    },
  });
}
