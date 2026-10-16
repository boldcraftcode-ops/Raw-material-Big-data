let token:string;
try{token=localStorage.getItem('rubber-workspace-token')||'';if(!token){token=crypto.randomUUID()+crypto.randomUUID();localStorage.setItem('rubber-workspace-token',token)}}catch{token=crypto.randomUUID()+crypto.randomUUID()}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
 const headers=new Headers(options.headers);headers.set('X-Workspace-Token',token);
 if(options.body && !(options.body instanceof FormData))headers.set('Content-Type','application/json');
 const response=await fetch(path,{...options,headers});
 if(!response.ok){let msg='Permintaan belum berhasil. Coba lagi.';try{const data=await response.json();msg=typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map((x:{msg:string})=>x.msg).join('; '):msg}catch{/* non-JSON error */}throw new Error(msg)}
 return response.json() as Promise<T>;
}
export async function download(path:string,name:string){
 const response=await fetch(path,{headers:{'X-Workspace-Token':token}});
 if(!response.ok){let msg='File tidak dapat diunduh.';try{msg=(await response.json()).detail||msg}catch{/* no body */}throw new Error(msg)}
 const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function dateText(value:string|null,options:Intl.DateTimeFormatOptions={day:'numeric',month:'short',year:'numeric'}){if(!value)return '—';return new Intl.DateTimeFormat('id-ID',options).format(new Date(value.length===10?value+'T12:00:00':value))}
export function money(value:string,currency:string){return new Intl.NumberFormat('id-ID',{style:'currency',currency,maximumFractionDigits:currency==='IDR'?0:4}).format(Number(value))}
export function bytes(value:number){return value>1024*1024?(value/1024/1024).toFixed(1)+' MB':Math.max(1,Math.round(value/1024))+' KB'}
export const statusLabel:Record<string,string>={queued:'Dalam antrean',parsing:'Membaca file',awaiting_mapping:'Perlu pemetaan',processing:'Memvalidasi',ready:'Siap ditelusuri',ready_with_issues:'Siap · perlu review',failed:'Gagal diproses',archived:'Raw tersimpan'};
export const typeLabel:Record<string,string>={workspace:'Lingkup workspace',organization:'Organisasi',material:'Material',location:'Lokasi',document:'Dokumen',source:'Sumber eksternal',signal:'Record eksternal'};
export const fieldLabel:Record<string,string>={date:'Tanggal',supplier:'Pemasok',price:'Harga',currency:'Mata uang',unit:'Unit harga',weight_basis:'Basis berat',drc:'KKK / DRC',quantity:'Kuantitas',price_kind:'Jenis harga'};

export const kindLabel:Record<string,string>={market_price:'Harga benchmark',production_stat:'Statistik produksi',weather_forecast:'Prakiraan cuaca',news_report:'Laporan berita'};
export const extractionLabel:Record<string,string>={indexed:'Teks terindeks',partial:'Indeks terbatas',raw_only:'Raw saja',extraction_failed:'Ekstraksi tidak berhasil'};
export function timeText(value:string|null){return dateText(value,{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Jakarta'})+' WIB'}
