import type { KindConfig } from './types';

export const ONTOLOGY_KINDS_STORAGE_KEY = 'ontology_kinds_config';

export const DEFAULT_KINDS_CONFIG: KindConfig[] = [
  {
    id: 'project',
    label: 'Project Root',
    description: 'Root platform & system architectures',
    shape: 'hexagon',
    baseRadius: 30,
    tier: 0,
  },
  {
    id: 'domain',
    label: 'Domain Chip',
    description: 'Primary architectural functional domains',
    shape: 'chip',
    baseRadius: 17,
    tier: 1,
  },
  {
    id: 'capability',
    label: 'Capability Disc',
    description: 'System modules, capabilities & features',
    shape: 'circle',
    baseRadius: 11,
    tier: 2,
  },
  {
    id: 'element',
    label: 'Element Pad',
    description: 'Underlying components, algorithms & via pads',
    shape: 'pad',
    baseRadius: 7,
    tier: 3,
  },
];
