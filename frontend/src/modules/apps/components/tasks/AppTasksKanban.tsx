import React, { useState, useMemo } from 'react';
import {
  Plus,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  Layers,
  AlertCircle,
  Loader2,
  RefreshCw,
  Sparkles,
  ListOrdered,
  FlaskConical,
  Rocket,
  PlayCircle,
  X,
} from 'lucide-react';
import { useToast } from '@/lib/toast';
import {
  AppTask,
  TaskStatus,
  TaskPriority,
  TASK_COLUMNS,
  useAppTasks,
  useCreateAppTask,
  useUpdateAppTask,
  useUpdateAppTaskStatus,
  useDeleteAppTask,
  CreateAppTaskPayload,
  UpdateAppTaskPayload,
} from '../../hooks/useAppTasks';
import { KanbanColumn } from './KanbanColumn';
import { CreateEditTaskModal } from './CreateEditTaskModal';

interface AppTasksKanbanProps {
  appId: string;
}

export const AppTasksKanban: React.FC<AppTasksKanbanProps> = ({ appId }) => {
  const toast = useToast();
  const { data: tasks = [], isLoading, error, refetch, isFetching } = useAppTasks(appId);

  const createTaskMutation = useCreateAppTask();
  const updateTaskMutation = useUpdateAppTask();
  const updateStatusMutation = useUpdateAppTaskStatus();
  const deleteTaskMutation = useDeleteAppTask();

  // Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<'ALL' | TaskPriority>('ALL');
  const [tagFilter, setTagFilter] = useState<string>('ALL');

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<AppTask | null>(null);
  const [modalDefaultStatus, setModalDefaultStatus] = useState<TaskStatus>('backlog');

  // Collect all unique tags for filter dropdown
  const allUniqueTags = useMemo(() => {
    const set = new Set<string>();
    tasks.forEach((t) => {
      if (Array.isArray(t.tags)) {
        t.tags.forEach((tag) => set.add(tag));
      }
    });
    return Array.from(set);
  }, [tasks]);

  // Filtered Tasks
  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      // Search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchTitle = t.title.toLowerCase().includes(query);
        const matchDesc = t.description?.toLowerCase().includes(query);
        const matchTags = Array.isArray(t.tags) && t.tags.some((tg) => tg.toLowerCase().includes(query));
        const matchAssignee = t.assignee?.toLowerCase().includes(query);
        if (!matchTitle && !matchDesc && !matchTags && !matchAssignee) {
          return false;
        }
      }

      // Priority filter
      if (priorityFilter !== 'ALL' && t.priority !== priorityFilter) {
        return false;
      }

      // Tag filter
      if (tagFilter !== 'ALL') {
        if (!Array.isArray(t.tags) || !t.tags.includes(tagFilter)) {
          return false;
        }
      }

      return true;
    });
  }, [tasks, searchQuery, priorityFilter, tagFilter]);

  // Tasks grouped by column
  const tasksByColumn = useMemo(() => {
    const grouped: Record<TaskStatus, AppTask[]> = {
      backlog: [],
      in_progress: [],
      testing: [],
      waiting_for_deployment: [],
      completed: [],
    };

    filteredTasks.forEach((t) => {
      if (grouped[t.status]) {
        grouped[t.status].push(t);
      } else {
        grouped.backlog.push(t);
      }
    });

    return grouped;
  }, [filteredTasks]);

  // Metrics calculations
  const totalTasksCount = tasks.length;
  const completedCount = tasks.filter((t) => t.status === 'completed').length;
  const inProgressCount = tasks.filter((t) => t.status === 'in_progress').length;
  const testingCount = tasks.filter((t) => t.status === 'testing').length;
  const pendingDeployCount = tasks.filter((t) => t.status === 'waiting_for_deployment').length;
  const completionPercentage = totalTasksCount > 0 ? Math.round((completedCount / totalTasksCount) * 100) : 0;

  // Handlers
  const handleOpenCreateModal = (defaultStatus: TaskStatus = 'backlog') => {
    setEditingTask(null);
    setModalDefaultStatus(defaultStatus);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (task: AppTask) => {
    setEditingTask(task);
    setModalDefaultStatus(task.status);
    setIsModalOpen(true);
  };

  const handleModalSubmit = async (payload: CreateAppTaskPayload | UpdateAppTaskPayload) => {
    if (editingTask) {
      await updateTaskMutation.mutateAsync({
        appId,
        taskId: editingTask.id,
        payload,
      });
      toast.success('Task updated successfully');
    } else {
      await createTaskMutation.mutateAsync({
        appId,
        payload: payload as CreateAppTaskPayload,
      });
      toast.success('Task created successfully');
    }
  };

  const handleStatusChange = (taskId: string, newStatus: TaskStatus) => {
    updateStatusMutation.mutate(
      {
        appId,
        taskId,
        status: newStatus,
      },
      {
        onSuccess: () => {
          toast.success(`Task moved to ${TASK_COLUMNS.find((c) => c.id === newStatus)?.title || newStatus}`);
        },
        onError: (err: any) => {
          toast.error(err?.response?.data?.detail || 'Failed to update task status');
        },
      }
    );
  };

  const handleDropTask = (taskId: string, targetStatus: TaskStatus) => {
    const existingTask = tasks.find((t) => t.id === taskId);
    if (!existingTask || existingTask.status === targetStatus) return;
    handleStatusChange(taskId, targetStatus);
  };

  const handleDeleteTask = (task: AppTask) => {
    if (window.confirm(`Are you sure you want to delete task "${task.title}"?`)) {
      deleteTaskMutation.mutate(
        { appId, taskId: task.id },
        {
          onSuccess: () => {
            toast.success('Task deleted successfully');
          },
          onError: (err: any) => {
            toast.error(err?.response?.data?.detail || 'Failed to delete task');
          },
        }
      );
    }
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setPriorityFilter('ALL');
    setTagFilter('ALL');
  };

  const hasActiveFilters = searchQuery.trim() !== '' || priorityFilter !== 'ALL' || tagFilter !== 'ALL';

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '400px',
          gap: 12,
          color: 'var(--color-text-muted, #64748b)',
        }}
      >
        <Loader2 size={28} className="spin" color="var(--color-primary, #2563eb)" />
        <span style={{ fontSize: '0.875rem' }}>Loading task tracking board...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: '24px',
          borderRadius: 8,
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          color: '#ef4444',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <AlertCircle size={20} />
          <span>Failed to load application tasks: {(error as any)?.message || 'Unknown error'}</span>
        </div>
        <button
          className="btn btn-outline"
          style={{ fontSize: '0.8rem', padding: '5px 12px' }}
          onClick={() => refetch()}
        >
          <RefreshCw size={13} /> Retry
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Top Header & Metrics Bar */}
      <div
        style={{
          background: 'var(--color-surface, #ffffff)',
          border: '1px solid var(--color-border, #e2e8f0)',
          borderRadius: 10,
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        {/* Row 1: Title & Actions */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--color-text, #0f172a)', margin: 0 }}>
                App Task Tracking
              </h2>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: 999,
                  background: 'rgba(37, 99, 235, 0.1)',
                  color: 'var(--color-primary, #2563eb)',
                }}
              >
                {totalTasksCount} Total Tasks
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--color-text-muted, #64748b)' }}>
              Manage feature backlogs, development progress, QA testing, deployment readiness, and completed deliverables.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              className="btn btn-outline"
              style={{ fontSize: '0.8rem', padding: '6px 12px' }}
              onClick={() => refetch()}
              disabled={isFetching}
              title="Refresh tasks"
            >
              <RefreshCw size={13} className={isFetching ? 'spin' : ''} />
              <span>Refresh</span>
            </button>

            <button
              className="btn btn-primary"
              style={{ fontSize: '0.82rem', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
              onClick={() => handleOpenCreateModal('backlog')}
            >
              <Plus size={15} />
              <span>New Task</span>
            </button>
          </div>
        </div>

        {/* Row 2: Metrics Chips & Progress Bar */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: 10,
            paddingTop: 12,
            borderTop: '1px solid var(--color-border, #f1f5f9)',
          }}
        >
          {/* Backlog */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(100, 116, 139, 0.06)',
              border: '1px solid rgba(100, 116, 139, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#64748b' }}>
              <ListOrdered size={14} />
              <span>Backlog</span>
            </div>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#475569' }}>
              {tasksByColumn.backlog.length}
            </span>
          </div>

          {/* In Progress */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(59, 130, 246, 0.08)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#3b82f6' }}>
              <PlayCircle size={14} />
              <span>In Progress</span>
            </div>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#2563eb' }}>
              {inProgressCount}
            </span>
          </div>

          {/* Testing */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#f59e0b' }}>
              <FlaskConical size={14} />
              <span>Testing</span>
            </div>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#d97706' }}>
              {testingCount}
            </span>
          </div>

          {/* Waiting for Deployment */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(139, 92, 246, 0.08)',
              border: '1px solid rgba(139, 92, 246, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#8b5cf6' }}>
              <Rocket size={14} />
              <span>Pending Deploy</span>
            </div>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#7c3aed' }}>
              {pendingDeployCount}
            </span>
          </div>

          {/* Completed */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#10b981' }}>
              <CheckCircle2 size={14} />
              <span>Completed</span>
            </div>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#059669' }}>
              {completedCount} ({completionPercentage}%)
            </span>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', flex: 1 }}>
          {/* Search Box */}
          <div className="search-bar-wrapper" style={{ width: 260 }}>
            <Search size={13} className="search-icon" />
            <input
              className="search-input"
              placeholder="Search tasks, tags, assignee..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <X
                size={13}
                style={{ cursor: 'pointer', color: 'var(--color-text-muted, #94a3b8)', marginRight: 6 }}
                onClick={() => setSearchQuery('')}
              />
            )}
          </div>

          {/* Priority Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted, #64748b)' }}>Priority:</span>
            <select
              className="input-field"
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value as any)}
              style={{ padding: '6px 10px', fontSize: '0.8rem', minWidth: '100px' }}
            >
              <option value="ALL">All Priorities</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {/* Tag Filter */}
          {allUniqueTags.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted, #64748b)' }}>Tag:</span>
              <select
                className="input-field"
                value={tagFilter}
                onChange={(e) => setTagFilter(e.target.value)}
                style={{ padding: '6px 10px', fontSize: '0.8rem', minWidth: '100px' }}
              >
                <option value="ALL">All Tags</option>
                {allUniqueTags.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Clear Filters button */}
          {hasActiveFilters && (
            <button
              type="button"
              className="btn btn-outline"
              style={{ fontSize: '0.75rem', padding: '5px 10px' }}
              onClick={handleClearFilters}
            >
              Clear Filters
            </button>
          )}
        </div>

        <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted, #64748b)' }}>
          Showing <b>{filteredTasks.length}</b> of <b>{totalTasksCount}</b> tasks
        </div>
      </div>

      {/* Kanban Board Columns Container */}
      <div
        style={{
          display: 'flex',
          gap: 14,
          overflowX: 'auto',
          paddingBottom: 16,
          alignItems: 'flex-start',
        }}
        className="sidebar-hover-scrollbar"
      >
        {TASK_COLUMNS.map((column) => (
          <KanbanColumn
            key={column.id}
            column={column}
            tasks={tasksByColumn[column.id] || []}
            onAddTask={(colStatus) => handleOpenCreateModal(colStatus)}
            onEditTask={handleOpenEditModal}
            onDeleteTask={handleDeleteTask}
            onStatusChange={handleStatusChange}
            onDropTask={handleDropTask}
          />
        ))}
      </div>

      {/* Create / Edit Modal */}
      <CreateEditTaskModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        task={editingTask}
        defaultStatus={modalDefaultStatus}
        onSubmit={handleModalSubmit}
      />
    </div>
  );
};
