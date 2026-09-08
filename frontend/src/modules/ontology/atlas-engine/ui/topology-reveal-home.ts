import { initHomeSpring, type HomeSpringState } from "../model/relayout-home";
import type { TopologyV2Tokens } from "../tokens/read-topology-v2-tokens";
import { recomputeWorldGeometry, type TopologyWorld } from "./topology-world";

export interface RevealHomeResult {
  world: TopologyWorld;
  springs: Map<string, HomeSpringState>;
}

/**
 * Creates the bootstrap reveal's mutable runtime world without changing the
 * world passed in. The rAF loop owns the returned world from this point onward;
 * callers holding the old world can still safely finish their frame.
 */
export function prepareRevealHome(
  world: TopologyWorld,
  tokens: TopologyV2Tokens,
  origin: { x: number; y: number },
): RevealHomeResult {
  const projectId = world.nodes.find((node: any) => node.kind === "org" || node.kind === "project")?.id ?? null;
  const nodes = world.nodes.map((node: any) => ({
    ...node,
    x: node.id === projectId ? node.x : origin.x,
    y: node.id === projectId ? node.y : origin.y,
  }));
  const nextWorld: TopologyWorld = {
    ...world,
    nodes,
    nodeById: new Map(nodes.map((node: any) => [node.id, node])),
    edges: world.edges.map((edge: any) => ({ ...edge })),
    bounds: { ...world.bounds },
    spineBounds: { ...world.spineBounds },
  };
  recomputeWorldGeometry(nextWorld, tokens);

  return {
    world: nextWorld,
    springs: new Map(nodes.map((node: any) => [node.id, initHomeSpring(node.x, node.y)])),
  };
}
