import type { KindConfig, TypeRelationConfig } from './types';
import {
  DEFAULT_KINDS_CONFIG,
  DEFAULT_TYPE_RELATIONS,
  ONTOLOGY_KINDS_STORAGE_KEY,
  ONTOLOGY_RELATIONS_STORAGE_KEY,
} from './defaults';

/**
 * Safely load configured kinds from localStorage with full fallback to defaults.
 */
export function loadKindsConfig(): KindConfig[] {
  if (typeof window === 'undefined') return DEFAULT_KINDS_CONFIG;
  try {
    const stored = localStorage.getItem(ONTOLOGY_KINDS_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (err) {
    console.warn('Failed to load ontology kinds configuration from storage:', err);
  }
  return DEFAULT_KINDS_CONFIG;
}

/**
 * Safely persist configured kinds to localStorage.
 */
export function saveKindsConfig(kinds: KindConfig[]): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(ONTOLOGY_KINDS_STORAGE_KEY, JSON.stringify(kinds));
  } catch (err) {
    console.error('Failed to persist ontology kinds configuration:', err);
  }
}

/**
 * Safely load configured type relations from localStorage with fallback.
 */
export function loadTypeRelations(): TypeRelationConfig[] {
  if (typeof window === 'undefined') return DEFAULT_TYPE_RELATIONS;
  try {
    const stored = localStorage.getItem(ONTOLOGY_RELATIONS_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (err) {
    console.warn('Failed to load ontology relations configuration from storage:', err);
  }
  return DEFAULT_TYPE_RELATIONS;
}

/**
 * Safely persist type relations to localStorage.
 */
export function saveTypeRelations(relations: TypeRelationConfig[]): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(ONTOLOGY_RELATIONS_STORAGE_KEY, JSON.stringify(relations));
  } catch (err) {
    console.error('Failed to persist ontology relations configuration:', err);
  }
}
