import type { ReactNode } from 'react';

/**
 * AppTable is the dense, technical table for operator/developer-facing screens.
 * Use it when the user needs to scan many rows, compare structured fields, or
 * work in data-heavy tools. For business-facing lists with a limited amount of
 * data and more comfortable row spacing, use `components/common/Table` instead.
 */

export type AppTableColumn<TRow> = {
  key: string;
  header: ReactNode;
  render: (row: TRow) => ReactNode;
  align?: 'left' | 'right' | 'center';
  width?: number | string;
  className?: string;
};

type AppTableProps<TRow> = {
  columns: AppTableColumn<TRow>[];
  rows: TRow[];
  rowKey: (row: TRow) => string | number;
  emptyText?: ReactNode;
  isLoading?: boolean;
  loadingRows?: number;
  onRowClick?: (row: TRow) => void;
  rowClassName?: (row: TRow) => string | undefined;
};

export function AppTable<TRow>({
  columns,
  rows,
  rowKey,
  emptyText = 'No data found.',
  isLoading = false,
  loadingRows = 3,
  onRowClick,
  rowClassName,
}: AppTableProps<TRow>) {
  return (
    <div className="app-table-wrap">
      <table className="app-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={column.className}
                style={{
                  textAlign: column.align ?? 'left',
                  width: column.width,
                }}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            Array.from({ length: loadingRows }).map((_, rowIndex) => (
              <tr key={`loading-${rowIndex}`}>
                {columns.map((column, columnIndex) => (
                  <td
                    key={column.key}
                    className={column.className}
                    style={{ textAlign: column.align ?? 'left' }}
                  >
                    <span
                      className="app-table-skeleton"
                      style={{
                        width: `${skeletonWidth(rowIndex, columnIndex)}%`,
                        marginLeft: column.align === 'right' ? 'auto' : undefined,
                      }}
                    />
                  </td>
                ))}
              </tr>
            ))
          ) : rows.length === 0 ? (
            <tr>
              <td className="app-table-empty" colSpan={columns.length}>
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                className={[
                  onRowClick ? 'is-clickable' : undefined,
                  rowClassName?.(row),
                ].filter(Boolean).join(' ') || undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={column.className}
                    style={{ textAlign: column.align ?? 'left' }}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function skeletonWidth(rowIndex: number, columnIndex: number) {
  const widths = [
    [18, 86, 42, 64, 52, 74, 30],
    [26, 74, 36, 54, 44, 66, 24],
    [14, 82, 48, 58, 38, 70, 28],
  ];
  return widths[rowIndex % widths.length][columnIndex % widths[0].length];
}
