import {useEffect, useId, useMemo, useRef, useState} from 'react';
import {forceSimulation, forceManyBody, forceCollide, forceLink, forceX, forceY, SimulationNodeDatum} from 'd3-force';
import {Focus, Minus, Plus, Scan, ChevronDown, Pause, Play, Orbit} from 'lucide-react';
import type {GraphData, GraphEdge, GraphNode, NodeType} from '../types';
import {curvePath, nodeTransform} from './galaxyMotion';
import {useGalaxyMotion} from './useGalaxyMotion';

const colors: Record<NodeType, string> = {workspace:'#9aebd5', organization:'#5ad6b8', material:'#b6a0f6', location:'#ecc080', document:'#78aef4', source:'#81d7ee', signal:'#edabca'};
type Positioned = GraphNode & SimulationNodeDatum & {tx: number; ty: number};
const stars = Array.from({length:100}, (_, i) => ({x:(i*137.508+17)%100, y:(i*i*11.39+9)%100, r:i%9===0?1.4:.65, opacity:.12+(i%5)*.07}));

export default function Galaxy({data, selectedId, onNode, onEdge, query, expanded=false, onExpand}: {
  data: GraphData; selectedId: string | null; onNode: (node: GraphNode) => void;
  onEdge: (edge: GraphEdge) => void; query: string; expanded?: boolean; onExpand: () => void;
}) {
  const wrap = useRef<HTMLDivElement>(null), svgRef = useRef<SVGSVGElement>(null);
  const motionNoteId = useId();
  const [size, setSize] = useState({w:800, h:440});
  const [zoom, setZoom] = useState(1), [pan, setPan] = useState({x:0, y:0});
  const [hover, setHover] = useState<string | null>(null), [focusedId, setFocusedId] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const dragging = useRef<{x: number; y: number; px: number; py: number} | null>(null);

  useEffect(() => {
    if (!wrap.current) return;
    const observer = new ResizeObserver(([entry]) => setSize({w:entry.contentRect.width, h:entry.contentRect.height}));
    observer.observe(wrap.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom(value => Math.max(.5, Math.min(2.6, value*(event.deltaY>0?.93:1.07))));
    };
    svg.addEventListener('wheel', wheel, {passive:false});
    return () => svg.removeEventListener('wheel', wheel);
  }, []);

  const layout = useMemo(() => {
    const radius = Math.min(size.w*.31, size.h*.38);
    const groups: Record<string, GraphNode[]> = {};
    for (const node of data.nodes) (groups[node.type]??=[]).push(node);
    const nodes: Positioned[] = data.nodes.map(node => {
      const i = groups[node.type].indexOf(node), total = groups[node.type].length;
      const angle = node.type==='material' ? i/total*Math.PI*2-.45 : node.type==='organization' ? i/total*Math.PI*2+.3 : node.type==='location' ? i/total*Math.PI*2+.5 : node.type==='source' ? i/total*Math.PI*2+.6 : i/total*Math.PI*2+1.15;
      const factor = node.type==='workspace' ? 0 : node.type==='material' ? .8 : node.type==='organization' ? 1.32 : node.type==='location' ? 1.95 : node.type==='source' ? .85 : node.type==='signal' ? 1.3+(i%7)*.035 : 1.1;
      const tx = Math.cos(angle)*radius*factor*1.06, ty = Math.sin(angle)*radius*factor*.64;
      return {...node, tx, ty, x:tx, y:ty, ...(node.type==='workspace'?{fx:0, fy:0}:{})};
    });
    const links = data.edges.map(edge => ({...edge}));
    let seed = 13;
    const random = () => (seed=Math.imul(seed,1664525)+1013904223>>>0)/4294967296;
    const simulation = forceSimulation<Positioned>(nodes).randomSource(random)
      .force('link', forceLink<Positioned, typeof links[number]>(links).id(node=>node.id).distance(95).strength(.04))
      .force('charge', forceManyBody().strength(-150))
      .force('collision', forceCollide<Positioned>().radius(node=>node.type==='workspace'?70:node.type==='material'?38:node.type==='signal'?14:26))
      .force('x', forceX<Positioned>(node=>node.tx).strength(.17))
      .force('y', forceY<Positioned>(node=>node.ty).strength(.21)).stop();
    simulation.tick(180);
    const extentX = Math.max(...nodes.map(node=>Math.abs(node.x||0)), 1), extentY = Math.max(...nodes.map(node=>Math.abs(node.y||0)), 1);
    const fit = Math.max(.05, Math.min(1, (size.w/2-65)/extentX, (size.h/2-37)/extentY));
    for (const node of nodes) {node.x=(node.x||0)*fit; node.y=(node.y||0)*fit}
    return {nodes, map:new Map(nodes.map(node=>[node.id, node]))};
  }, [data, size]);

  const motion = useGalaxyMotion({nodes:layout.nodes, edges:data.edges, size, stageRef:wrap, draggingRef:dragging, selectedId, hoveredId:hover, focusedId});
  const hoveredId = hover || focusedId;
  const highlighted = useMemo(() => {
    const ids = new Set<string>();
    if (query.trim()) {
      for (const node of data.nodes) if (node.label.toLocaleLowerCase().includes(query.toLocaleLowerCase())) ids.add(node.id);
    } else if (filter!=='all') {
      for (const node of data.nodes) if (node.type===filter) ids.add(node.id);
    } else if (hoveredId || selectedId) ids.add(hoveredId || selectedId!);
    return ids;
  }, [query, filter, hoveredId, selectedId, data]);
  const neighbors = new Set(highlighted);
  for (const edge of data.edges) if (highlighted.has(edge.source)||highlighted.has(edge.target)) {neighbors.add(edge.source); neighbors.add(edge.target)}
  const reset = () => {setZoom(1); setPan({x:0, y:0})};
  const motionLabel = motion.reduced ? 'Gerak dibatasi' : motion.enabled ? 'Jeda gerak' : 'Gerakkan';

  return <div className={'galaxy-card '+(expanded?'galaxy-expanded':'')}>
    <div className="panel-heading">
      <div><h3>Peta pengetahuan <span className="tiny-badge">GALAXY</span></h3><p>{data.total_nodes} node <span>·</span> {data.total_edges} hubungan berbukti / konteks</p></div>
      <button className="icon-button" onClick={onExpand} title={expanded?'Tutup layar penuh':'Perbesar galaksi'} aria-label={expanded?'Tutup layar penuh':'Perbesar galaksi'}><Scan size={17}/></button>
    </div>
    <div className="galaxy-toolbar">
      <div className="graph-filter"><span className="green-dot"/>Terhubung ke arsip</div>
      <div className="galaxy-toolbar-actions">
        <button className={'graph-motion-toggle '+(motion.enabled&&!motion.reduced?'is-on':'')} onClick={motion.toggle}
          disabled={motion.reduced||!motion.hasEntities} aria-pressed={motion.enabled&&!motion.reduced}
          aria-label={motion.reduced?'Animasi mengikuti pengaturan kurangi gerakan':motion.enabled?'Jeda animasi galaksi':'Aktifkan animasi galaksi'}
          title={motion.reduced?'Animasi nonaktif mengikuti pengaturan kurangi gerakan pada perangkat.':!motion.hasEntities?'Gerak tersedia setelah ada entitas data.':'Gerak visual acak. Node diam saat disorot atau dipilih; data dan bukti tidak berubah.'}>
          {motion.enabled&&!motion.reduced?<Pause size={12}/>:<Play size={12}/>}<span>{motionLabel}</span>
        </button>
        <label className="select-compact"><select value={filter} onChange={event=>setFilter(event.target.value)} aria-label="Sorot jenis entitas">
          <option value="all">Semua entitas</option><option value="organization">Organisasi</option><option value="material">Material</option><option value="location">Lokasi</option><option value="document">Dokumen</option><option value="source">Sumber eksternal</option><option value="signal">Record eksternal</option>
        </select><ChevronDown size={12}/></label>
      </div>
    </div>
    <div className="galaxy-stage" ref={wrap} data-motion={motion.status}>
      <svg ref={svgRef} viewBox={`0 0 ${size.w} ${size.h}`} aria-label="Galaksi hubungan data karet alam. Gunakan tab untuk memilih node; roda mouse untuk zoom." aria-describedby={motionNoteId}
        onPointerDown={event=>{
          if ((event.target as Element).closest('[data-interactive]')) return;
          dragging.current={x:event.clientX, y:event.clientY, px:pan.x, py:pan.y};
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={event=>{const drag=dragging.current; if(drag) setPan({x:drag.px+event.clientX-drag.x, y:drag.py+event.clientY-drag.y})}}
        onPointerUp={()=>{dragging.current=null}} onPointerCancel={()=>{dragging.current=null}} onLostPointerCapture={()=>{dragging.current=null}}>
        <defs>
          <radialGradient id="nebula"><stop offset="0" stopColor="#244a65" stopOpacity=".4"/><stop offset=".5" stopColor="#333760" stopOpacity=".16"/><stop offset="1" stopColor="#101c2e" stopOpacity="0"/></radialGradient>
          <radialGradient id="core-glow"><stop stopColor="#67e7bf" stopOpacity=".15"/><stop offset="1" stopColor="#67e7bf" stopOpacity="0"/></radialGradient>
        </defs>
        <ellipse cx={size.w*.5} cy={size.h*.48} rx={size.w*.5} ry={size.h*.49} fill="url(#nebula)"/>
        {stars.map((star,i)=><circle key={i} cx={star.x/100*size.w} cy={star.y/100*size.h} r={star.r} fill="#b7cbe6" opacity={star.opacity}/>)}
        <g className="graph-universe" transform={`translate(${size.w/2+pan.x},${size.h/2+pan.y}) scale(${zoom})`}>
          {[.56,.86,1.16].map(radius=><ellipse key={radius} rx={Math.min(size.w*.4,size.h*.62)*radius} ry={size.h*.34*radius} transform="rotate(-15)" stroke="#6686ad" strokeOpacity=".12" strokeDasharray="2 8" fill="none"/>)}
          {data.edges.map(edge=>{
            const source=layout.map.get(edge.source), target=layout.map.get(edge.target);
            if (!source||!target) return null;
            const active=highlighted.has(source.id)||highlighted.has(target.id), dim=highlighted.size>0&&!active;
            const path=curvePath({x:source.x||0, y:source.y||0}, {x:target.x||0, y:target.y||0});
            return <g key={edge.id} ref={element=>motion.registerEdge(edge.id,element)} data-interactive="edge" data-edge-id={edge.id} data-source-id={edge.source} data-target-id={edge.target} className="graph-edge" onClick={()=>onEdge(edge)}>
              <path d={path} fill="none" stroke={active?colors[source.type]:'#7c91b0'} strokeOpacity={dim?.055:active?.5:.16} strokeWidth={active?1.3:.8} strokeDasharray={(edge.evidence_ids.length||edge.record_ids?.length)?'':'3 6'}/>
              <path d={path} fill="none" stroke="transparent" strokeWidth="10"><title>{edge.label}{edge.count?` · ${edge.count} observasi`:''}</title></path>
            </g>;
          })}
          {layout.nodes.map(node=>{
            const active=node.id===selectedId||node.id===hover||node.id===focusedId, context=neighbors.has(node.id), dim=highlighted.size>0&&!context;
            const color=colors[node.type], radius=node.type==='workspace'?37:node.type==='material'?10:node.type==='document'?6:node.type==='signal'?3.5:node.type==='source'?8:5;
            const label=node.label.length>25?node.label.slice(0,23)+'…':node.label;
            return <g key={node.id} ref={element=>motion.registerNode(node.id,element)} data-interactive="node" data-node-id={node.id} data-node-type={node.type}
              role="button" tabIndex={0} aria-label={`${node.label}. ${node.count} observasi. Buka detail.`}
              transform={nodeTransform({x:node.x||0,y:node.y||0})} className="graph-node" opacity={dim?.24:1}
              onPointerDown={event=>event.stopPropagation()} onClick={()=>onNode(node)} onPointerEnter={()=>setHover(node.id)} onPointerLeave={()=>setHover(null)}
              onFocus={()=>setFocusedId(node.id)} onBlur={()=>setFocusedId(null)}
              onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onNode(node)}}}>
              <title>{node.label}</title>
              {node.type==='workspace'?<>
                <circle r="86" fill="url(#core-glow)"/><circle r="49" stroke={color} strokeOpacity=".1" fill="none"/>
                <circle r="39" fill="#16363e" stroke={color} strokeOpacity=".7"/>
                <text textAnchor="middle" y="-1" fill="#dbfff2" fontSize="12" fontWeight="600">Karet alam</text>
                <text textAnchor="middle" y="15" fill="#75bfae" fontSize="7" letterSpacing="2">WORKSPACE</text>
              </>:<>
                <circle r={radius+8} fill={color} opacity={active?.18:.065}/>
                {active&&<circle r={radius+13} fill="none" stroke={color} strokeOpacity=".35" strokeDasharray="2 3"/>}
                {node.type==='document'?<rect x="-5" y="-5" width="10" height="10" rx="2" fill={color} transform="rotate(45)"/>:<circle r={radius} fill={color}/>}
                {(node.type==='material'||node.type==='source'||(node.type==='location'&&data.nodes.filter(n=>n.type==='location').length<=8)||active||highlighted.has(node.id))&&
                  <text textAnchor="middle" y={(node.y||0)>0&&node.type!=='organization'?radius+19:-(radius+11)} fill={active?'#eff5ff':color} fontSize={node.type==='material'?11:9} fontWeight={node.type==='material'?600:450} stroke="#101a2a" strokeWidth="3" paintOrder="stroke">{active?node.label:label}</text>}
                <circle className="graph-node-hit-area" r={Math.max(radius+9,13)} fill="transparent"/>
              </>}
            </g>;
          })}
        </g>
      </svg>
      {!data.nodes.length&&<div className="graph-empty"><Focus size={34}/><h3>Galaksimu dimulai dari satu data.</h3><p>Arsipkan raw, petakan pembelian, atau pantau sumber eksternal. Setiap hubungan tetap memiliki konteks dan bukti.</p></div>}
      <div className="graph-coordinates">NATURAL RUBBER / KNOWLEDGE SPACE</div>
      <div className="graph-controls">
        <button onClick={()=>setZoom(value=>Math.min(2.6,value+.15))} aria-label="Perbesar"><Plus size={15}/></button><span>{Math.round(zoom*100)}%</span>
        <button onClick={()=>setZoom(value=>Math.max(.5,value-.15))} aria-label="Perkecil"><Minus size={15}/></button><i/>
        <button onClick={reset} aria-label="Atur ulang posisi"><Focus size={16}/></button>
      </div>
    </div>
    <div className="graph-footer">
      <div className="graph-footer-main">
        <div className="legend">{(['organization','material','location','document','source','signal'] as NodeType[]).map(type=><span key={type}><i style={{background:colors[type]}}/>{type==='organization'?'Organisasi':type==='material'?'Material':type==='location'?'Lokasi':type==='source'?'Sumber':type==='signal'?'Record':'Dokumen'}</span>)}</div>
        <span className="graph-hint">Klik node untuk menelusuri</span>
      </div>
      <p className="graph-motion-note" id={motionNoteId}><Orbit size={11}/><span>Gerak acak hanya visual, bukan perubahan data.{motion.reduced?' Animasi nonaktif mengikuti pengaturan perangkat.':!motion.enabled?' Gerak dijeda.':' Node diam saat disorot atau dipilih.'}</span></p>
    </div>
    {data.truncated&&<div className="graph-limit">{data.coverage_note||'Tampilan dibatasi 160 node / 400 relasi. Gunakan pencarian untuk menelusuri arsip lain.'}</div>}
  </div>;
}
