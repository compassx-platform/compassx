import React from 'react';
import type { ChartType } from '@/types/dashboard';
import type { VisualizationConfigProps } from './types';
import TableConfigSection from './sections/TableConfigSection';
import CounterConfigSection from './sections/CounterConfigSection';
import StandardChartConfigSection from './sections/StandardChartConfigSection';

/**
 * Registry mapping ChartType to its dedicated configuration panel component.
 * Follows Open/Closed Principle (OCP) — new visualization types can be registered
 * without modifying monolithic switch statements.
 */
const visualizationConfigMap: Map<ChartType, React.ComponentType<VisualizationConfigProps>> = new Map([
  ['table', TableConfigSection],
  ['counter', CounterConfigSection],
]);

/**
 * Register a custom visualization config component for a chart type.
 */
export function registerVisualizationConfig(
  type: ChartType,
  component: React.ComponentType<VisualizationConfigProps>
) {
  visualizationConfigMap.set(type, component);
}

/**
 * Retrieve the visualization config component for a given chart type.
 * Defaults to StandardChartConfigSection for Cartesian / standard chart types.
 */
export function getVisualizationConfigComponent(
  type: ChartType
): React.ComponentType<VisualizationConfigProps> {
  return visualizationConfigMap.get(type) || StandardChartConfigSection;
}
