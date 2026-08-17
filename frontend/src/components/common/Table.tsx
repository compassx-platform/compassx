import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

/**
 * Table is the business-facing table pattern, extracted from the Agents page.
 * Use it for approachable lists with a limited amount of data, generous spacing,
 * readable labels, and row-level actions. For dense technical/operator screens,
 * use `AppTable` instead.
 */

export type TableColumn<TRow> = {
  key: string;
  header: ReactNode;
  width?: string | number;
  align?: 'left' | 'center' | 'right';
  render: (row: TRow) => ReactNode;
};

export type TableAction<TRow> = {
  label: string;
  icon?: LucideIcon;
  onClick: (row: TRow) => void;
  variant?: 'default' | 'danger';
  hidden?: (row: TRow) => boolean;
  disabled?: (row: TRow) => boolean;
};

type TablePrimaryAction<TRow> = {
  label: string | ((row: TRow) => string);
  icon?: LucideIcon;
  onClick: (row: TRow) => void;
  hidden?: (row: TRow) => boolean;
};

export type TableProps<TRow> = {
  columns: TableColumn<TRow>[];
  rows: TRow[];
  keyExtractor: (row: TRow) => string;
  primaryAction?: TablePrimaryAction<TRow>;
  visibleActions?: TableAction<TRow>[];
  rowActions?: TableAction<TRow>[];
  emptyState?: ReactNode;
  loading?: boolean;
  errorState?: ReactNode;
  error?: boolean;
  toolbar?: ReactNode;
  actionsColumnWidth?: string | number;
  onRowClick?: (row: TRow) => void;
};

export function Table<TRow>({
  columns,
  rows,
  keyExtractor,
  primaryAction,
  visibleActions = [],
  rowActions = [],
  emptyState,
  loading = false,
  error = false,
  errorState,
  toolbar,
  actionsColumnWidth = '16%',
  onRowClick,
}: TableProps<TRow>) {
  const hasActions = Boolean(primaryAction) || visibleActions.length > 0 || rowActions.length > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {toolbar}
      <div className="admin-table-wrap">
        {loading ? (
          <div className="table-empty">Loading...</div>
        ) : error ? (
          errorState ?? <div className="table-empty error">Failed to load data.</div>
        ) : rows.length === 0 ? (
          emptyState ?? <div className="table-empty">No data.</div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th
                    key={column.key}
                    style={{
                      width: column.width,
                      textAlign: column.align ?? 'left',
                    }}
                  >
                    {column.header}
                  </th>
                ))}
                {hasActions && <th style={{ width: actionsColumnWidth }} />}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <TableRow
                  key={keyExtractor(row)}
                  row={row}
                  columns={columns}
                  primaryAction={primaryAction}
                  visibleActions={visibleActions}
                  rowActions={rowActions}
                  hasActions={hasActions}
                  onRowClick={onRowClick}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function TableRow<TRow>({
  row,
  columns,
  primaryAction,
  visibleActions,
  rowActions,
  hasActions,
  onRowClick,
}: {
  row: TRow;
  columns: TableColumn<TRow>[];
  primaryAction?: TablePrimaryAction<TRow>;
  visibleActions: TableAction<TRow>[];
  rowActions: TableAction<TRow>[];
  hasActions: boolean;
  onRowClick?: (row: TRow) => void;
}) {
  const PrimaryIcon = primaryAction?.icon;

  return (
    <tr
      className={onRowClick ? 'table-row-clickable' : undefined}
      onClick={onRowClick ? () => onRowClick(row) : undefined}
    >
      {columns.map((column) => (
        <td key={column.key} style={{ textAlign: column.align ?? 'left' }}>
          {column.render(row)}
        </td>
      ))}
      {hasActions && (
        <td onClick={(event) => event.stopPropagation()}>
          <div className="row-actions">
            {primaryAction && !primaryAction.hidden?.(row) && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => primaryAction.onClick(row)}
              >
                {PrimaryIcon && <PrimaryIcon size={14} />}
                {typeof primaryAction.label === 'function' ? primaryAction.label(row) : primaryAction.label}
              </button>
            )}
            {[...visibleActions, ...rowActions]
              .filter((action) => !action.hidden?.(row))
              .map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.label}
                    type="button"
                    className={`btn-icon${action.variant === 'danger' ? ' btn-icon-danger' : ''}`}
                    title={action.label}
                    aria-label={action.label}
                    onClick={() => action.onClick(row)}
                    disabled={action.disabled?.(row)}
                  >
                    {Icon && <Icon size={14} />}
                  </button>
                );
              })}
          </div>
        </td>
      )}
    </tr>
  );
}
