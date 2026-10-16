import type {NodeType} from '../types';

/** Presentation geometry only. Never writes to graph records, counts or evidence. */
export interface MotionAnchor {id: string; type: NodeType; x?: number; y?: number}
export interface Point {x: number; y: number}
export interface MotionBody extends Point {
  id: string;
  type: NodeType;
  anchorX: number;
  anchorY: number;
  amplitude: number;
  duration: number;
  seed: number;
  elapsed: number;
  limitX: number;
  limitY: number;
}
export type MotionState = Map<string, MotionBody>;

const amplitudes: Record<NodeType, number> = {
  workspace: 0, organization: 19, material: 14, location: 17,
  document: 21, source: 22, signal: 24,
};
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
const finite = (value: number | undefined, fallback = 0) => Number.isFinite(value) ? value! : fallback;

function hash(value: string): number {
  let seed = 2166136261;
  for (let i = 0; i < value.length; i++) seed = Math.imul(seed ^ value.charCodeAt(i), 16777619);
  return seed >>> 0;
}

/** Seeded pseudo-randomness gives each actual entity its own independent route. */
function unit(seed: number, salt: number): number {
  let value = seed ^ Math.imul(salt + 1, 0x9e3779b1);
  value = Math.imul(value ^ (value >>> 16), 0x7feb352d);
  value = Math.imul(value ^ (value >>> 15), 0x846ca68b);
  return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
}

function waypoint(body: MotionBody, index: number): Point {
  if (!index) return {x: 0, y: 0}; // No initial jump when animation starts.
  const angle = unit(body.seed, index * 2) * Math.PI * 2;
  const radius = body.amplitude * (.45 + unit(body.seed, index * 2 + 1) * .55);
  return {x: Math.cos(angle) * radius, y: Math.sin(angle) * radius};
}

function position(body: MotionBody): void {
  const phase = body.elapsed / body.duration;
  const index = Math.floor(phase);
  const fraction = phase - index;
  // Quintic interpolation: continuous velocity/acceleration, not jitter or teleporting.
  const blend = fraction * fraction * fraction * (fraction * (fraction * 6 - 15) + 10);
  const from = waypoint(body, index), to = waypoint(body, index + 1);
  body.x = clamp(body.anchorX + from.x + (to.x - from.x) * blend, -body.limitX, body.limitX);
  body.y = clamp(body.anchorY + from.y + (to.y - from.y) * blend, -body.limitY, body.limitY);
}

export function createMotionState(
  anchors: readonly MotionAnchor[],
  size: {w: number; h: number},
  previous: ReadonlyMap<string, MotionBody> = new Map(),
): MotionState {
  const width = Math.max(1, finite(size.w, 800)), height = Math.max(1, finite(size.h, 440));
  const scale = clamp(Math.min(width / 760, height / 420), .3, 1.4);
  const limitX = Math.max(0, width / 2 - 28), limitY = Math.max(0, height / 2 - 28);
  const points = anchors.map(node => ({...node,
    x: node.type === 'workspace' ? 0 : clamp(finite(node.x), -limitX, limitX),
    y: node.type === 'workspace' ? 0 : clamp(finite(node.y), -limitY, limitY),
  }));
  const states: MotionState = new Map();
  for (const node of points) {
    let nearest = Infinity;
    for (const other of points) {
      if (node.id !== other.id) nearest = Math.min(nearest, Math.hypot(node.x - other.x, node.y - other.y));
    }
    const old = previous.get(node.id), seed = hash(node.id);
    const body: MotionBody = {
      id: node.id, type: node.type, anchorX: node.x, anchorY: node.y,
      // Small, crowd-aware movement preserves the original knowledge-map structure.
      amplitude: Math.min(amplitudes[node.type] * scale, nearest * .28),
      duration: (node.type === 'signal' ? 3.7 : 4.6) + unit(seed, 0) * 3.8,
      seed, elapsed: old?.type === node.type ? Math.max(0, finite(old.elapsed)) : 0,
      x: node.x, y: node.y, limitX, limitY,
    };
    position(body);
    states.set(node.id, body);
  }
  return states;
}

export function advanceMotion(states: MotionState, seconds: number, locked: ReadonlySet<string> = new Set()): void {
  // Slow down gracefully after a delayed frame instead of jumping forward.
  const delta = clamp(finite(seconds), 0, .1);
  if (!delta) return;
  for (const body of states.values()) {
    if (body.type === 'workspace' || locked.has(body.id)) continue;
    body.elapsed += delta;
    position(body);
  }
}

export function nodeTransform(point: Point): string {
  return `translate(${point.x.toFixed(3)},${point.y.toFixed(3)})`;
}

/** Visible curve and pointer hit-area always share exactly the same endpoints. */
export function curvePath(source: Point, target: Point): string {
  const mx = (source.x + target.x) / 2 + 12, my = (source.y + target.y) / 2 - 14;
  return `M${source.x.toFixed(3)} ${source.y.toFixed(3)} Q${mx.toFixed(3)} ${my.toFixed(3)} ${target.x.toFixed(3)} ${target.y.toFixed(3)}`;
}
