import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// Test the production TS module without an extra test framework or emitted files.
const source = readFileSync(new URL('../src/components/galaxyMotion.ts', import.meta.url), 'utf8');
const {outputText} = ts.transpileModule(source, {compilerOptions:{target:ts.ScriptTarget.ES2022, module:ts.ModuleKind.ESNext}});
const {createMotionState, advanceMotion, curvePath, nodeTransform} = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const size = {w:800, h:440};
const anchors = () => [
  {id:'workspace', type:'workspace', x:0, y:0},
  {id:'source-wb', type:'source', x:105, y:20},
  {id:'source-fao', type:'source', x:-110, y:25},
  {id:'record-1', type:'signal', x:175, y:-100},
  {id:'record-2', type:'signal', x:-165, y:-100},
  {id:'document', type:'document', x:5, y:150},
];
const step = (state, count=90, locked=new Set()) => {for(let i=0;i<count;i++) advanceMotion(state, 1/30, locked)};
const positions = state => [...state.values()].map(node => [node.id,node.x,node.y,node.elapsed]);

 test('Starts at the existing layout, with a stationary workspace', () => {
  const original=anchors(), state=createMotionState(original,size);
  for(const node of original) {
    assert.equal(state.get(node.id).x,node.x);
    assert.equal(state.get(node.id).y,node.y);
  }
  step(state,450);
  assert.deepEqual([state.get('workspace').x,state.get('workspace').y,state.get('workspace').elapsed],[0,0,0]);
});

test('Real entities take different, smooth pseudo-random routes', () => {
  const state=createMotionState(anchors(),size);
  step(state,120);
  for(const node of anchors().filter(node=>node.type!=='workspace')) {
    const current=state.get(node.id);
    assert.ok(Math.hypot(current.x-node.x,current.y-node.y)>.01, node.id+' should move');
  }
  const wb=state.get('source-wb'), fao=state.get('source-fao');
  assert.notEqual(wb.x-wb.anchorX,fao.x-fao.anchorX);
  const before=positions(state);
  advanceMotion(state,1/30);
  for(const [id,x,y] of before) assert.ok(Math.hypot(state.get(id).x-x,state.get(id).y-y)<1);
});

test('Motion never mutates graph inputs or fabricates graph metadata', () => {
  const graph=anchors().map(node=>({...node,count:4,evidence_ids:['existing-proof']}));
  const original=structuredClone(graph);
  const state=createMotionState(graph,size);
  step(state,1000);
  assert.deepEqual(graph,original);
  assert.equal(state.size,graph.length);
  assert.ok([...state.keys()].every(id=>graph.some(node=>node.id===id)));
});

test('Long-running paths stay inside their bounded neighbourhood and viewport', () => {
  for(const viewport of [{w:340,h:330},size,{w:1440,h:900}]) {
    const state=createMotionState(anchors(),viewport);
    for(let i=0;i<2100;i++) {
      advanceMotion(state,.1);
      for(const node of state.values()) {
        assert.ok(Number.isFinite(node.x)&&Number.isFinite(node.y));
        assert.ok(Math.abs(node.x)<=node.limitX+1e-9);
        assert.ok(Math.abs(node.y)<=node.limitY+1e-9);
        assert.ok(Math.hypot(node.x-node.anchorX,node.y-node.anchorY)<=node.amplitude+1e-8);
      }
    }
  }
});

test('Dense graphs get smaller drift instead of collapsing their layout', () => {
  const graph=Array.from({length:160},(_,i)=>({id:'dense-'+i,type:'signal',x:(i%16)*12-90,y:Math.floor(i/16)*12-54}));
  const state=createMotionState(graph,size);
  for(const node of state.values()) assert.ok(node.amplitude<=12*.28+1e-9);
  for(let tick=0;tick<240;tick++) {
    advanceMotion(state,.1);
    for(let i=1;i<graph.length;i++) {
      const a=state.get(graph[i-1].id),b=state.get(graph[i].id);
      assert.ok(Math.hypot(a.x-b.x,a.y-b.y)>.43*Math.hypot(a.anchorX-b.anchorX,a.anchorY-b.anchorY));
    }
  }
});

test('Hovered, focused and selected entities freeze while other entities keep moving', () => {
  const state=createMotionState(anchors(),size);
  step(state,90);
  const locked=new Set(['source-wb','record-1','document']);
  const before=new Map(positions(state).map(([id,...values])=>[id,values]));
  step(state,210,locked);
  for(const id of locked) assert.deepEqual([state.get(id).x,state.get(id).y,state.get(id).elapsed],before.get(id));
  assert.notEqual(state.get('record-2').elapsed,before.get('record-2')[2]);
});

test('Released entities resume from their frozen pose without a time jump', () => {
  const state=createMotionState(anchors(),size);
  step(state,50);
  const locked=new Set(['source-wb']);
  step(state,300,locked);
  const node=state.get('source-wb'),before={x:node.x,y:node.y,time:node.elapsed};
  advanceMotion(state,1/30);
  assert.ok(Math.hypot(node.x-before.x,node.y-before.y)<1);
  assert.ok(Math.abs(node.elapsed-before.time-1/30)<1e-9);
});

test('Polling the same graph preserves clocks and exact positions', () => {
  const state=createMotionState(anchors(),size);
  step(state,180);
  const refreshed=createMotionState(structuredClone(anchors()),size,state);
  assert.deepEqual(positions(refreshed),positions(state));
});

test('New and removed graph IDs have correct lifecycle; changed types restart safely', () => {
  const state=createMotionState(anchors(),size);
  step(state,90);
  const next=createMotionState([{id:'source-wb',type:'source',x:105,y:20},{id:'new',type:'signal',x:190,y:70}],size,state);
  assert.equal(next.size,2);
  assert.equal(next.has('record-1'),false);
  assert.equal(next.get('source-wb').elapsed,state.get('source-wb').elapsed);
  assert.equal(next.get('new').elapsed,0);
  const changed=createMotionState([{id:'source-wb',type:'document',x:105,y:20}],size,state);
  assert.equal(changed.get('source-wb').elapsed,0);
});

test('Resize/fullscreen preserves clocks and fits geometry in the new viewport', () => {
  const state=createMotionState(anchors(),size);
  step(state,180);
  const resized=createMotionState(anchors(),{w:340,h:330},state);
  for(const node of resized.values()) {
    assert.equal(node.elapsed,state.get(node.id).elapsed);
    assert.ok(Math.abs(node.x)<=142&&Math.abs(node.y)<=137);
  }
});

test('Empty, workspace-only and zero-distance graphs remain finite', () => {
  assert.equal(createMotionState([],size).size,0);
  const state=createMotionState([{id:'workspace',type:'workspace',x:20,y:30},{id:'same',type:'signal',x:0,y:0}],{w:0,h:0});
  step(state,200);
  for(const node of state.values()) assert.ok(Number.isFinite(node.x)&&Number.isFinite(node.y));
  assert.equal(state.get('same').amplitude,0);
  assert.equal(state.get('workspace').x,0);
});

test('Invalid or delayed frame timing cannot cause teleporting', () => {
  const state=createMotionState(anchors(),size),before=positions(state);
  for(const delta of [NaN,Infinity,-1,0]) advanceMotion(state,delta);
  assert.deepEqual(positions(state),before);
  advanceMotion(state,60);
  assert.equal(state.get('source-wb').elapsed,.1);
});

test('Visible edge endpoints and hit areas use the exact displayed node geometry', () => {
  const state=createMotionState(anchors(),size);
  step(state,160);
  const a=state.get('source-wb'),b=state.get('record-1');
  const path=curvePath(a,b),numbers=path.match(/-?\d+(?:\.\d+)?/g).map(Number);
  assert.deepEqual(numbers.slice(0,2),[Number(a.x.toFixed(3)),Number(a.y.toFixed(3))]);
  assert.deepEqual(numbers.slice(-2),[Number(b.x.toFixed(3)),Number(b.y.toFixed(3))]);
  assert.equal(nodeTransform(a),`translate(${a.x.toFixed(3)},${a.y.toFixed(3)})`);
});

test('Seeded routes are reproducible, but different IDs do not share a trajectory', () => {
  const first=createMotionState(anchors(),size),second=createMotionState(anchors(),size);
  step(first,299);step(second,299);
  assert.deepEqual(positions(first),positions(second));
  const one=createMotionState([{id:'one',type:'source',x:90,y:0}],size);
  const two=createMotionState([{id:'two',type:'source',x:90,y:0}],size);
  step(one,160);step(two,160);
  assert.notDeepEqual([one.get('one').x,one.get('one').y],[two.get('two').x,two.get('two').y]);
});
