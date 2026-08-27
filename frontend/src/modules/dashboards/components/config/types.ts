import type { ChartConfig, Dataset, Widget } from '@/types/dashboard';

export interface VisualizationConfigProps {
  widget: Widget;
  config: ChartConfig;
  dataset?: Dataset;
  fieldOptions: Array<{ value: string; label: string }>;
  getFieldType: (fieldName: string) => string;
  patch: (patch: Partial<ChartConfig>) => void;
  patchAxis: (axis: 'xAxis' | 'yAxis' | 'y2Axis', p: Record<string, unknown>) => void;
}
