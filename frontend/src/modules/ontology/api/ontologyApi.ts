/**
 * API client for Ontology Metamodel and Knowledge Graph database persistence.
 */

import api from '@/lib/api';
import type { KindConfig, TypeRelationConfig, GraphValidationResult } from '../config/types';
import type { OntologyDataset } from '../types/ontology';

// ─── Entity Types API ─────────────────────────────────────────────────────────

export async function fetchOntologyTypes(): Promise<KindConfig[]> {
  const res = await api.get<any[]>('/ontology/schema/types');
  return res.data.map(t => ({
    id: t.id,
    label: t.label,
    description: t.description || undefined,
    shape: t.shape,
    baseRadius: t.base_radius,
    tier: t.tier,
    color: t.color || undefined,
    icon: t.icon || undefined,
    is_system: t.is_system,
  }));
}

export async function createOntologyType(data: KindConfig): Promise<KindConfig> {
  const res = await api.post<any>('/ontology/schema/types', {
    id: data.id,
    label: data.label,
    description: data.description,
    shape: data.shape,
    base_radius: data.baseRadius,
    tier: data.tier,
    color: data.color,
    icon: data.icon,
  });
  return {
    id: res.data.id,
    label: res.data.label,
    description: res.data.description,
    shape: res.data.shape,
    baseRadius: res.data.base_radius,
    tier: res.data.tier,
    color: res.data.color,
    icon: res.data.icon,
    is_system: res.data.is_system,
  };
}

export async function updateOntologyType(id: string, data: Partial<KindConfig>): Promise<KindConfig> {
  const payload: Record<string, any> = {};
  if (data.label !== undefined) payload.label = data.label;
  if (data.description !== undefined) payload.description = data.description;
  if (data.shape !== undefined) payload.shape = data.shape;
  if (data.baseRadius !== undefined) payload.base_radius = data.baseRadius;
  if (data.tier !== undefined) payload.tier = data.tier;
  if (data.color !== undefined) payload.color = data.color;
  if (data.icon !== undefined) payload.icon = data.icon;

  const res = await api.put<any>(`/ontology/schema/types/${encodeURIComponent(id)}`, payload);
  return {
    id: res.data.id,
    label: res.data.label,
    description: res.data.description,
    shape: res.data.shape,
    baseRadius: res.data.base_radius,
    tier: res.data.tier,
    color: res.data.color,
    icon: res.data.icon,
    is_system: res.data.is_system,
  };
}

export async function deleteOntologyType(id: string): Promise<void> {
  await api.delete(`/ontology/schema/types/${encodeURIComponent(id)}`);
}

// ─── Type Relationships (Metamodel) API ───────────────────────────────────────

export async function fetchTypeRelations(): Promise<TypeRelationConfig[]> {
  const res = await api.get<TypeRelationConfig[]>('/ontology/schema/relations');
  return res.data;
}

export async function createTypeRelation(data: TypeRelationConfig): Promise<TypeRelationConfig> {
  const res = await api.post<TypeRelationConfig>('/ontology/schema/relations', {
    source_type_id: data.source_type_id,
    relation_type: data.relation_type,
    target_type_id: data.target_type_id,
    is_hierarchical: data.is_hierarchical ?? false,
    description: data.description,
  });
  return res.data;
}

export async function updateTypeRelation(relationId: number, data: Partial<TypeRelationConfig>): Promise<TypeRelationConfig> {
  const payload: Record<string, any> = {};
  if (data.source_type_id !== undefined) payload.source_type_id = data.source_type_id;
  if (data.relation_type !== undefined) payload.relation_type = data.relation_type;
  if (data.target_type_id !== undefined) payload.target_type_id = data.target_type_id;
  if (data.is_hierarchical !== undefined) payload.is_hierarchical = data.is_hierarchical;
  if (data.description !== undefined) payload.description = data.description;

  const res = await api.put<TypeRelationConfig>(`/ontology/schema/relations/${relationId}`, payload);
  return res.data;
}

export async function deleteTypeRelation(relationId: number): Promise<void> {
  await api.delete(`/ontology/schema/relations/${relationId}`);
}

// ─── Knowledge Graph DB API ───────────────────────────────────────────────────

export async function fetchActiveKnowledgeGraph(graphId: string = 'default'): Promise<OntologyDataset> {
  const res = await api.get<any>(`/ontology/graph/active?graph_id=${encodeURIComponent(graphId)}`);
  return {
    name: res.data.name,
    version: res.data.version,
    description: res.data.description,
    yaml_content: res.data.yaml_content,
    nodes: (res.data.nodes || []).map((n: any) => ({
      id: n.id,
      kind: n.kind,
      uid: n.uid,
      title: n.title,
      description: n.description,
      parentId: n.parentId || n.parent_id || null,
      domainId: n.domainId || n.domain_id || null,
      path: n.path,
      tags: n.tags || [],
      status: n.status || 'active',
      ...n.properties,
    })),
    edges: (res.data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || e.source_id,
      target: e.target || e.target_id,
      type: e.type || e.relation_type,
      description: e.description,
      ...e.properties,
    })),
  };
}

export async function validateKnowledgeGraph(payload: {
  yaml_content?: string;
  dataset?: OntologyDataset;
}): Promise<GraphValidationResult> {
  const res = await api.post<GraphValidationResult>('/ontology/graph/validate', payload);
  return res.data;
}

export async function importYamlKnowledgeGraph(payload: {
  yaml_content?: string;
  dataset?: OntologyDataset;
  graph_id?: string;
  name?: string;
}): Promise<OntologyDataset> {
  const res = await api.post<any>('/ontology/graph/import-yaml', payload);
  return {
    name: res.data.name,
    version: res.data.version,
    description: res.data.description,
    yaml_content: res.data.yaml_content,
    nodes: (res.data.nodes || []).map((n: any) => ({
      id: n.id,
      kind: n.kind,
      uid: n.uid,
      title: n.title,
      description: n.description,
      parentId: n.parentId || n.parent_id || null,
      domainId: n.domainId || n.domain_id || null,
      path: n.path,
      tags: n.tags || [],
      status: n.status || 'active',
      ...n.properties,
    })),
    edges: (res.data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || e.source_id,
      target: e.target || e.target_id,
      type: e.type || e.relation_type,
      description: e.description,
      ...e.properties,
    })),
  };
}

export async function addGraphNode(node: {
  id: string;
  kind: string;
  title: string;
  description?: string;
  parentId?: string | null;
  domainId?: string | null;
  path?: string;
  tags?: string[];
  status?: string;
  properties?: Record<string, any>;
}): Promise<OntologyDataset> {
  const res = await api.post<any>('/ontology/graph/nodes', node);
  return {
    name: res.data.name,
    version: res.data.version,
    description: res.data.description,
    nodes: (res.data.nodes || []).map((n: any) => ({
      id: n.id,
      kind: n.kind,
      uid: n.uid,
      title: n.title,
      description: n.description,
      parentId: n.parentId || n.parent_id || null,
      domainId: n.domainId || n.domain_id || null,
      path: n.path,
      tags: n.tags || [],
      status: n.status || 'active',
      ...n.properties,
    })),
    edges: (res.data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || e.source_id,
      target: e.target || e.target_id,
      type: e.type || e.relation_type,
      description: e.description,
      ...e.properties,
    })),
  };
}

export async function updateGraphNode(
  nodeId: string,
  updates: {
    title?: string;
    kind?: string;
    description?: string;
    parentId?: string | null;
    domainId?: string | null;
    path?: string;
    tags?: string[];
    status?: string;
    properties?: Record<string, any>;
  }
): Promise<OntologyDataset> {
  const res = await api.put<any>(`/ontology/graph/nodes/${encodeURIComponent(nodeId)}`, updates);
  return {
    name: res.data.name,
    version: res.data.version,
    description: res.data.description,
    nodes: (res.data.nodes || []).map((n: any) => ({
      id: n.id,
      kind: n.kind,
      uid: n.uid,
      title: n.title,
      description: n.description,
      parentId: n.parentId || n.parent_id || null,
      domainId: n.domainId || n.domain_id || null,
      path: n.path,
      tags: n.tags || [],
      status: n.status || 'active',
      ...n.properties,
    })),
    edges: (res.data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || e.source_id,
      target: e.target || e.target_id,
      type: e.type || e.relation_type,
      description: e.description,
      ...e.properties,
    })),
  };
}

export async function deleteGraphNode(nodeId: string): Promise<OntologyDataset> {
  const res = await api.delete<any>(`/ontology/graph/nodes/${encodeURIComponent(nodeId)}`);
  return {
    name: res.data.name,
    version: res.data.version,
    description: res.data.description,
    nodes: (res.data.nodes || []).map((n: any) => ({
      id: n.id,
      kind: n.kind,
      uid: n.uid,
      title: n.title,
      description: n.description,
      parentId: n.parentId || n.parent_id || null,
      domainId: n.domainId || n.domain_id || null,
      path: n.path,
      tags: n.tags || [],
      status: n.status || 'active',
      ...n.properties,
    })),
    edges: (res.data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || e.source_id,
      target: e.target || e.target_id,
      type: e.type || e.relation_type,
      description: e.description,
      ...e.properties,
    })),
  };
}

export async function addGraphEdge(edge: {
  id?: string;
  source: string;
  target: string;
  type: string;
  description?: string;
  properties?: Record<string, any>;
}): Promise<OntologyDataset> {
  const res = await api.post<any>('/ontology/graph/edges', edge);
  return {
    name: res.data.name,
    version: res.data.version,
    description: res.data.description,
    nodes: (res.data.nodes || []).map((n: any) => ({
      id: n.id,
      kind: n.kind,
      uid: n.uid,
      title: n.title,
      description: n.description,
      parentId: n.parentId || n.parent_id || null,
      domainId: n.domainId || n.domain_id || null,
      path: n.path,
      tags: n.tags || [],
      status: n.status || 'active',
      ...n.properties,
    })),
    edges: (res.data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || e.source_id,
      target: e.target || e.target_id,
      type: e.type || e.relation_type,
      description: e.description,
      ...e.properties,
    })),
  };
}

export async function deleteGraphEdge(edgeId: string): Promise<OntologyDataset> {
  const res = await api.delete<any>(`/ontology/graph/edges/${encodeURIComponent(edgeId)}`);
  return {
    name: res.data.name,
    version: res.data.version,
    description: res.data.description,
    nodes: (res.data.nodes || []).map((n: any) => ({
      id: n.id,
      kind: n.kind,
      uid: n.uid,
      title: n.title,
      description: n.description,
      parentId: n.parentId || n.parent_id || null,
      domainId: n.domainId || n.domain_id || null,
      path: n.path,
      tags: n.tags || [],
      status: n.status || 'active',
      ...n.properties,
    })),
    edges: (res.data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || e.source_id,
      target: e.target || e.target_id,
      type: e.type || e.relation_type,
      description: e.description,
      ...e.properties,
    })),
  };
}
