import {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import type {RefObject} from 'react';
import type {GraphEdge} from '../types';
import {advanceMotion, createMotionState, curvePath, nodeTransform} from './galaxyMotion';
import type {MotionAnchor, MotionBody, MotionState} from './galaxyMotion';

const PREFERENCE = 'rubber-galaxy-motion';
type NodeBinding = {element: SVGGElement; body: MotionBody; last: string};
type EdgeBinding = {paths: SVGPathElement[]; source: MotionBody; target: MotionBody; last: string};

export function useGalaxyMotion({nodes, edges, size, stageRef, draggingRef, selectedId, hoveredId, focusedId}: {
  nodes: readonly MotionAnchor[];
  edges: readonly GraphEdge[];
  size: {w: number; h: number};
  stageRef: RefObject<HTMLDivElement | null>;
  draggingRef: RefObject<unknown>;
  selectedId: string | null;
  hoveredId: string | null;
  focusedId: string | null;
}) {
  const [enabled, setEnabled] = useState(() => {
    try {return localStorage.getItem(PREFERENCE) !== 'paused'} catch {return true}
  });
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [visible, setVisible] = useState(() => typeof document === 'undefined' || !document.hidden);
  const [inView, setInView] = useState(true);
  const nodeElements = useRef(new Map<string, SVGGElement>());
  const edgeElements = useRef(new Map<string, SVGGElement>());
  const state = useRef<MotionState>(new Map());
  const bindings = useRef<{nodes: NodeBinding[]; edges: EdgeBinding[]}>({nodes: [], edges: []});
  const locked = useRef<ReadonlySet<string>>(new Set());

  const registerNode = useCallback((id: string, element: SVGGElement | null) => {
    if (element) nodeElements.current.set(id, element); else nodeElements.current.delete(id);
  }, []);
  const registerEdge = useCallback((id: string, element: SVGGElement | null) => {
    if (element) edgeElements.current.set(id, element); else edgeElements.current.delete(id);
  }, []);
  const paint = useCallback(() => {
    for (const binding of bindings.current.nodes) {
      const transform = nodeTransform(binding.body);
      if (transform !== binding.last) {binding.element.setAttribute('transform', transform); binding.last = transform}
    }
    for (const binding of bindings.current.edges) {
      const path = curvePath(binding.source, binding.target);
      if (path !== binding.last) {
        for (const element of binding.paths) element.setAttribute('d', path);
        binding.last = path;
      }
    }
  }, []);

  useLayoutEffect(() => {
    locked.current = new Set([selectedId, hoveredId, focusedId].filter((id): id is string => Boolean(id)));
  }, [selectedId, hoveredId, focusedId]);

  useLayoutEffect(() => {
    // Keep each existing entity's clock through polling; remove disappeared IDs.
    // Rebind only on geometry/data changes, never on every animation frame.
    state.current = createMotionState(nodes, size, state.current);
    const next: typeof bindings.current = {nodes: [], edges: []};
    for (const [id, body] of state.current) {
      const element = nodeElements.current.get(id);
      if (element) next.nodes.push({element, body, last: ''});
    }
    for (const edge of edges) {
      const element = edgeElements.current.get(edge.id), source = state.current.get(edge.source), target = state.current.get(edge.target);
      if (element && source && target) next.edges.push({
        paths: Array.from(element.querySelectorAll<SVGPathElement>('path')), source, target, last: '',
      });
    }
    bindings.current = next;
    paint();
  }, [nodes, edges, size.w, size.h, paint]);

  useEffect(() => {
    try {localStorage.setItem(PREFERENCE, enabled ? 'running' : 'paused')} catch {/* Browser storage is optional. */}
  }, [enabled]);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media.matches);
    media.addEventListener('change', update); update();
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  }, []);
  useEffect(() => {
    if (!stageRef.current || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting && entry.intersectionRatio >= .05), {threshold: [.05]});
    observer.observe(stageRef.current);
    return () => observer.disconnect();
  }, [stageRef]);

  const hasEntities = nodes.some(node => node.type !== 'workspace');
  const running = enabled && !reduced && visible && inView && hasEntities;
  useEffect(() => {
    if (!running) return;
    let handle = 0, last = 0, disposed = false;
    const frame = (now: number) => {
      if (disposed) return;
      if (!last) last = now;
      // About 30 geometry updates/second; no React state updates per frame.
      if (now - last >= 32) {
        const delta = (now - last) / 1000;
        last = now;
        if (!draggingRef.current) {advanceMotion(state.current, delta, locked.current); paint()}
      }
      handle = requestAnimationFrame(frame);
    };
    handle = requestAnimationFrame(frame);
    return () => {disposed = true; cancelAnimationFrame(handle)};
  }, [running, draggingRef, paint]);

  return {
    enabled, reduced, hasEntities, registerNode, registerEdge,
    toggle: () => setEnabled(value => !value),
    status: reduced ? 'reduced' : !hasEntities ? 'empty' : !enabled ? 'paused' : !visible || !inView ? 'offscreen' : 'running',
  };
}
