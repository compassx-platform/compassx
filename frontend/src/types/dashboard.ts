/** Dashboard domain types */

// ── Grid layout item (react-grid-layout) ─────────────────────────────────────

export interface GridItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}

// ── Enums ─────────────────────────────────────────────────────────────────────

export type WidgetType =
  | 'chart'
  | 'html'
  | 'filter'
  | 'text'
  | 'image';

export type ChartType =
  | 'area' | 'bar' | 'box' | 'bubble' | 'choropleth'
  | 'cohort' | 'combo' | 'counter' | 'funnel' | 'heatmap'
  | 'histogram' | 'line' | 'pie' | 'pivot' | 'point_map'
  | 'sankey' | 'scatter' | 'table' | 'waterfall';

export type ParamType = 'string' | 'date' | 'datetime' | 'decimal' | 'integer';

export type FilterScope = 'global' | 'page' | 'widget';

export type FilterWidgetType =
  | 'multi_value' | 'single_value' | 'date_picker'
  | 'date_range' | 'text_entry' | 'range_slider';

export type FilterApplyMode = 'instant' | 'button';

// ── Dataset ───────────────────────────────────────────────────────────────────

export interface DatasetParam {
  keyword: string;
  type: ParamType;
  displayName?: string;
  defaultValue?: string;
  allowMultiple?: boolean;
}

export interface DatasetField {
  name: string;
  type: string;
  comment?: string;
}

export interface Dataset {
  id: string;
  dashboardId: string;
  name: string;
  sql: string;
  params: DatasetParam[];
  schema: DatasetField[];
}

// ── Axis + formatting config ──────────────────────────────────────────────────

export interface AxisConfig {
  title?: string;
  showTitle?: boolean;
  showValues?: boolean;
  min?: number;
  max?: number;
  reversed?: boolean;
  logScale?: boolean;
  labelAngle?: number;
  sortOrder?: 'asc' | 'desc' | 'alpha' | 'field' | 'custom';
  scaleType?: 'continuous' | 'categorical';
  transform?: 'NONE' | 'SUM' | 'AVG' | 'MEDIAN' | 'MIN' | 'MAX' | 'COUNT' | 'COUNT DISTINCT' | 'VAR' | 'STD' | 'PERCENTILE' | 'FIRST' | 'LAST';
  displayName?: string;
  errorBar?: boolean;
  sortByField?: string;
  sortByOrder?: 'asc' | 'desc';
  tickCount?: number;
}

export interface NumberFormat {
  type: 'number' | 'currency' | 'percent';
  abbreviation?: 'none' | 'compact' | 'scientific';
  decimals?: number;
  groupSeparator?: boolean;
  negativeStyle?: 'minus' | 'parens' | 'red';
  currencySymbol?: string;
}

export interface LegendConfig {
  show?: boolean;
  title?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export interface Annotation {
  id: string;
  axis: 'x' | 'y';
  value: number | string;
  label?: string;
  color?: string;
}

export interface SeriesColor {
  field: string;
  color: string;
}

// ── Chart config ──────────────────────────────────────────────────────────────

export interface ChartConfig {
  chartType: ChartType;
  datasetId?: string;
  xField?: string;
  yFields?: string[];
  colorField?: string;
  sizeField?: string;
 xAxis?: AxisConfig;
 yAxis?: AxisConfig;
  y2Axis?: AxisConfig;
  numberFormat?: NumberFormat;
  legend?: LegendConfig;
  seriesColors?: SeriesColor[];
  seriesTitles?: Array<{ field: string; title: string }>;
  showGridlines?: boolean;
  showValueLabels?: boolean;
  valueLabelField?: string;
  tooltipFields?: string[];
  lineThickness?: number;
  annotations?: Annotation[];
  aiForecast?: boolean;
  facetField?: string;
  facetRows?: number;
  facetCols?: number;
  // combo: secondary y fields on line
  y2Fields?: string[];
  enableSeriesSwitcher?: boolean;
  // counter
  comparisonField?: string;
  showSparkline?: boolean;
  conditionalFormatting?: Array<{ min?: number; max?: number; color: string }>;
  // map
  latField?: string;
  lonField?: string;
  geoField?: string;
  geoLevel?: 'country' | 'state' | 'county';
  // table
  pageSize?: number;
  showSearch?: boolean;
  wrapText?: boolean;
  showRowNumbers?: boolean;
  // layout sub-type
  layout?: 'stack' | '100stack' | 'group';
}

// ── Static widget-level filter ────────────────────────────────────────────────

export interface WidgetFilter {
  id: string;
  field: string;
  filterType: FilterWidgetType;
  value: unknown;
}

// ── HTML report widget ───────────────────────────────────────────────────────

export interface HtmlReportConfig {
  datasetId?: string;
  reportType?: 'dgr';
  title?: string;
  subtitle?: string;
  alias?: string;
}

// ── Widget ────────────────────────────────────────────────────────────────────

export interface Widget {
  id: string;
  pageId: string;
  widgetType: WidgetType;
  title?: string;
  gridItem: GridItem;
  // chart-specific
  chartConfig?: ChartConfig;
  // html/page-specific
  htmlConfig?: HtmlReportConfig;
  staticFilters?: WidgetFilter[];
  // filter widget
  filterConfig?: FilterWidgetConfig;
  // text/image widget
  content?: string;
}

// ── Filter widget config ──────────────────────────────────────────────────────

export interface FilterWidgetConfig {
  scope: FilterScope;
  filterType: FilterWidgetType;
  field?: string;
  datasetIds: string[];
  paramKeyword?: string;
  defaultValue?: unknown;
  allowAll?: boolean;
  // text entry
  matchMode?: 'contains' | 'exact' | 'starts_with';
  caseSensitive?: boolean;
  // date range presets
  presets?: string[];
  // dynamic/static list for param
  listMode?: 'dynamic' | 'static';
  staticOptions?: string[];
  dynamicDatasetId?: string;
  dynamicField?: string;
}

// ── Drill-through ─────────────────────────────────────────────────────────────

export interface DrillThrough {
  sourceWidgetId: string;
  targetPageId: string;
  fieldMappings: Array<{ sourceField: string; targetFilterId: string }>;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export interface DashboardPage {
  id: string;
  dashboardId: string;
  name: string;
  order: number;
  layout: GridItem[];
  drillThroughs?: DrillThrough[];
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export type DashboardPermissionMode = 'individual' | 'shared';

export interface FontSettings {
  family?: string;
  case?: string;
  size?: number | 'Auto';
  weight?: string;
  color?: string;
}

export interface DashboardTheme {
  preset?: string;
  previewMode?: 'light' | 'dark';
  canvasBg?: string;
  widgetBg?: string;
  widgetBorder?: string;
  selectionColor?: string;
  cornerRadius?: number;
  padding?: number;
  margin?: number;
  shadow?: number;
  titleAlignment?: 'left' | 'center' | 'right';
  fontTarget?: 'default' | 'title' | 'description' | 'field_title' | 'field_value';
  fonts?: {
    default?: FontSettings;
    title?: FontSettings;
    description?: FontSettings;
    field_title?: FontSettings;
    field_value?: FontSettings;
  };
  axisColor?: string;
  gridColor?: string;
  verticalAlignment?: 'top' | 'center' | 'bottom';
  palette?: string[];
}

export interface DashboardSettings {
  theme?: DashboardTheme;
  locale?: string;
  filterApplyMode?: FilterApplyMode;
  tags?: Array<{ key: string; value: string }>;
  genieEnabled?: boolean;
  genieSpaceUrl?: string;
  showGridLines?: boolean;
  gridCols?: number;
  gridRowHeight?: number;
  minWidgetHeight?: number;
}

export interface DashboardMeta {
  id: string;
  name: string;
  folderId?: string;
  isDraft: boolean;
  publishedAt?: string;
  createdBy?: string;
  createdAt: string;
  updatedAt: string;
  permissionMode: DashboardPermissionMode;
}

export interface Dashboard extends DashboardMeta {
  pages: DashboardPage[];
  widgets: Widget[];
  datasets: Dataset[];
  settings?: DashboardSettings;
}

// ── Filter state ──────────────────────────────────────────────────────────────

export type FilterValue = string | string[] | number | [number, number] | [string, string] | null;

export interface FilterState {
  [filterId: string]: FilterValue;
}

export interface ParamState {
  [keyword: string]: FilterValue;
}
