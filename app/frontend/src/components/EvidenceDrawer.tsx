import {useEffect,useState} from 'react';
import {X,ArrowUpRight,Download,FileText,ShieldCheck,Fingerprint,GitBranch,Info,LoaderCircle} from 'lucide-react';
import {api,bytes,dateText,download,money} from '../api';
import type {Evidence} from '../types';
export default function EvidenceDrawer({id,onClose,notify}:{id:string;onClose:()=>void;notify:(message:string)=>void}){
 const[data,setData]=useState<Evidence|null>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;api<Evidence>('/api/evidence/'+id).then(d=>{if(active)setData(d)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[id]);
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose()};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key)},[onClose]);
 return <div className="drawer-shade" onMouseDown={onClose}><aside className="evidence-drawer" role="dialog" aria-modal="true" aria-labelledby="evidence-title" onMouseDown={e=>e.stopPropagation()}><div className="drawer-heading"><div><span className="eyebrow">PROVENANCE</span><h2 id="evidence-title">Jejak bukti</h2></div><button className="icon-button" onClick={onClose} aria-label="Tutup bukti"><X size={20}/></button></div>
 {!data&&!error&&<div className="loading-panel"><LoaderCircle className="spin" size={24}/>Memuat bukti…</div>}{error&&<div className="error-box">{error}</div>}
 {data&&<div className="drawer-content">
  {data.is_demo&&<div className="sample-note"><Info size={15}/>Data simulasi. Bukan transaksi atau harga pasar nyata.</div>}
  <div className="evidence-summary"><span className="mini-label">OBSERVASI HARGA</span><h3>{data.material}{data.grade&&<span> / {data.grade}</span>}</h3><div className="big-price">{money(data.price,data.currency)}<small>/{data.unit}</small></div><div className="price-tags"><span>Basis {data.weight_basis}</span><span>{data.price_kind.replaceAll('_',' ')}</span></div><p>{data.supplier} <span>·</span> {dateText(data.observed_date)}</p></div>
  <div className="validation-note"><ShieldCheck size={17}/><div><strong>Tervalidasi aturan, bukan audit kebenaran</strong><p>Nilai dibaca dari unggahan dan lolos aturan format. Identitas, transaksi, dan lokasi belum diverifikasi eksternal.</p></div></div>
  <section className="evidence-section"><h4><FileText size={16}/>Sumber asli</h4><div className="source-box"><strong>{data.filename}</strong><p>Versi {data.version_no} <span>·</span> {bytes(data.size_bytes)}</p><div className="source-location"><span>Lembar <b>{data.sheet}</b></span><span>Baris <b>{data.row_no}</b></span><span>Pemetaan <b>r{data.mapping_rev}</b></span></div><div className={'active-source '+(!data.is_active?'archived':'')}><i/>{data.is_active?'Versi aktif dalam galaksi':'Versi arsip — bukan data aktif'}</div></div></section>
  <section className="evidence-section"><h4><GitBranch size={16}/>Nilai dan transformasi</h4><dl className="evidence-dl"><div><dt>Harga sumber</dt><dd>{data.price} {data.currency}/{data.unit}</dd></div><div><dt>Basis berat</dt><dd>{data.weight_basis}</dd></div><div><dt>KKK / DRC</dt><dd>{data.drc_percent?data.drc_percent+'%':'Tidak tersedia'}</dd></div><div><dt>Lokasi dilaporkan</dt><dd>{data.location||'Tidak tersedia'}</dd></div>{data.dry_equivalent&&<div><dt>Ekuivalen kandungan kering</dt><dd>{money(data.dry_equivalent,data.currency)}/kg</dd></div>}</dl>{data.transform_notes.map((n,i)=><p className="transform-note" key={i}>{n}</p>)}<p className="muted small">Ekuivalen kering tidak menyetarakan grade, biaya pengolahan, atau harga pasar.</p></section>
  <section className="evidence-section"><h4>Sel sumber <span className="tiny-badge">TIDAK DIUBAH</span></h4><div className="raw-cell-list">{data.raw_values.map((r,i)=><div key={i}><span>{r.label}</span><code>{r.value==null?'—':String(r.value)}</code></div>)}</div></section>
  <section className="evidence-section"><h4><Fingerprint size={16}/>Integritas arsip</h4><span className="mini-label">SHA-256</span><code className="hash-block">{data.sha256}</code></section>
  <button className="button primary full" onClick={()=>download('/api/versions/'+data.version_id+'/raw',data.filename).catch(e=>notify(e.message))}><Download size={16}/>Unduh file asli<ArrowUpRight size={15}/></button>
 </div>}
 </aside></div>
}
