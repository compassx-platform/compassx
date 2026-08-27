# Dashboard Module — Fundamental Design & Architecture Rules

This document outlines the core architectural principles, UI philosophy, and data handling standards for the **Dashboard Module** (`frontend/src/modules/dashboards/`). All future agents and developers modifying this module must adhere to these rules.

---

## 1. Modular Configuration Architecture (SOLID / Open-Closed Principle)
- **Decoupled Visualization Configs**: The widget configuration panel (`ChartConfigPanel.tsx`) must never be a monolithic file.
- Dedicated configuration sections for each visualization type reside under `components/config/sections/` (e.g. `CounterConfigSection.tsx`, `TableConfigSection.tsx`, `StandardChartConfigSection.tsx`, `HtmlConfigSection.tsx`).
- Sections are mapped dynamically via `components/config/vizConfigRegistry.ts`. Adding new chart types must only require adding a new section and registering it in the registry.

---

## 2. Minimalist UI Philosophy (No Empty Dropdowns by Default)
- **Clean Section Rows**: When a field (e.g., metric value, comparison field, X-axis, Y-axis) is not selected, **never render an open empty `<Select>` dropdown**.
- Instead, render only the clean section header with a **`+`** button on the right.
- Clicking the **`+`** button reveals the column selector.
- Once selected, render a compact **Field Pill** (`FieldPill.tsx`) with a remove button `—`. Removing the pill restores the clean `+` state.

---

## 3. Popover Field Configuration & Column Switching
- Clicking a **Field Pill** opens `AxisConfigPopover.tsx`.
- **Interactive Field Header**: Inside the popover, the "Field" section must be an interactive dropdown allowing the user to switch to any column in the dataset directly without deleting the pill.
- **Transform Only**: Selecting a transform (SUM, AVG, MIN, MAX, COUNT, etc.) updates **only** the `transform` property. It must **never overwrite or mutate the custom `displayName`**.
- **Metric-Specific Cleanliness**: For metric/counter widgets, hide chart-only options in the popover (`Display name`, `Scale type`, `Error bar`).

---

## 4. Metric / Counter Widget Standards
- **Dynamic Pill Label**: The metric pill displays `SUM(column_name)` as a visual indicator of the active transform, but leaves the underlying column and subtitle settings clean.
- **Canvas Label Display**: Under the big metric number on the dashboard canvas, **do not automatically display the column name or transform name**. Text is only displayed if the user explicitly enters a custom **"Sublabel / Caption"** (`xField`).
- **Units Beside the Number**: Support displaying units (e.g. `ms`, `GB`, `kg`, `pts`, `users`, `units`, `hrs`, `%`) rendered right beside the metric number with baseline typography alignment.
- **Comparison Field**: Has independent transformation support (`comparisonTransform`), dynamic pill label, and delta calculation.
- **Tooltips**: Avoid static multi-line helper text. Use a clean **`?`** (`HelpCircle`) icon with hover tooltip.

---

## 5. Segmented Buttons & Compact Controls
- For small option sets (3–4 choices such as Type: `Number | Currency | Percent`, Abbreviation: `None | Compact | Scientific`, Decimals: `All | Exact | Max`), use **direct segmented buttons** instead of select dropdowns.
- **No Outer Border Boxes**: Segmented controls must be compact (`3px 6px` padding, `0.72rem` font size) without heavy outer container boxes or borders.
- **Decimal Modes**:
  - `All`: Full precision as-is without forced rounding or padding.
  - `Exact`: Exact number of decimal places (pads zeros, e.g. `12.50`).
  - `Max`: Up to maximum decimal places without forced trailing zeros (e.g. `12.5` or `12.56`).
  - When `Exact` or `Max` is selected, show the `Decimal Places` numeric input.

---

## 6. Live Series Aggregations & Data Transforms
- All aggregations are computed dynamically across dataset rows via `frontend/src/modules/dashboards/utils/dataTransforms.ts` (`aggregateValues`).
- Aggregation functions (`SUM`, `AVG`, `COUNT`, `COUNT DISTINCT`, `MIN`, `MAX`, `MEDIAN`, `FIRST`, `LAST`, `VAR`, `STD`, `PERCENTILE`) must handle both numeric fields and non-numeric string/ID fields without failing.

---

## 7. Real-Time Query Execution & Cache Invalidation
- **SQL Dependency in Query Key**: All widget components must pass `dataset?.sql` to `useDatasetQuery(datasetId, params, filters, enabled, dataset?.sql)` so any SQL change in the dataset immediately updates the React Query key and runs the updated query.
- **Zero Stale Time**: `staleTime` is set to `0` in `useDatasetQuery` to prevent stale memory cache when switching tabs or editing.
- **Save Invalidation**: Saving, editing, or deleting datasets in `DataPanel.tsx` or `useSaveDashboard` must invalidate `['dataset-query']` and `['dataset-schema']` caches.

---

## 8. Store Mutation Safety (Zustand)
- In `ChartConfigPanel.tsx`, `patch` and `patchAxis` must fetch the latest live widget from `useDashboardStore.getState().activeDashboard` before merging updates to prevent stale closure overwrites during rapid sequential updates.
