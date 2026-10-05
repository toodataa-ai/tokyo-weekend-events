export const WARDS = [
  '千代田区','中央区','港区','新宿区','文京区','台東区','墨田区','江東区','品川区','目黒区','大田区',
  '世田谷区','渋谷区','中野区','杉並区','豊島区','北区','荒川区','板橋区','練馬区','足立区','葛飾区','江戸川区'
];

export function isoLocal(d){
  const y=d.getFullYear(), m=String(d.getMonth()+1).padStart(2,'0'), day=String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${day}`;
}

export function defaultDate(){
  const t = new Date();
  const wd = t.getDay();
  if(wd === 6 || wd === 0) return isoLocal(t);
  return isoLocal(new Date(t.getFullYear(), t.getMonth(), t.getDate() + (6-wd)));
}

export function saturdayOf(dateStr){
  const [y,m,d] = dateStr.split('-').map(Number);
  const base = new Date(y,m-1,d);
  const wd = base.getDay();
  const diff = wd === 6 ? 0 : wd === 0 ? -1 : 6-wd;
  return isoLocal(new Date(y,m-1,d+diff));
}

export function fmtRange(sat,sun){
  const s=new Date(sat+'T00:00:00'), e=new Date(sun+'T00:00:00');
  const w=['日','月','火','水','木','金','土'];
  return `${s.getFullYear()}/${s.getMonth()+1}/${s.getDate()}(${w[s.getDay()]}) 〜 ${e.getMonth()+1}/${e.getDate()}(${w[e.getDay()]})`;
}

export function normalizeText(value){
  return String(value ?? '').normalize('NFKC').toLocaleLowerCase('ja-JP').replace(/\s+/g,' ').trim();
}

export function eventSearchText(ev){
  return normalizeText([
    ev.name, ev.ward, ev.venue, ev.description, ev.price, ev.period, ev.time,
    ...(Array.isArray(ev.categories) ? ev.categories : []),
    ev.family_fit?.reason, ev.family_fit?.age,
    ev.reservation?.note
  ].filter(Boolean).join(' '));
}

export function filterEvents(events, filters={}){
  const ward = filters.ward || '__all__';
  const q = normalizeText(filters.q || '');
  return (events || []).filter(ev => {
    if(ward !== '__all__' && ev.ward !== ward) return false;
    if(q && !eventSearchText(ev).includes(q)) return false;
    return true;
  });
}

export function countsByWard(events){
  const counts = Object.fromEntries(WARDS.map(w => [w,0]));
  (events || []).forEach(ev => { if(ev.ward in counts) counts[ev.ward] += 1; });
  return counts;
}

export function readFiltersFromUrl(){
  const p = new URLSearchParams(location.search);
  const ward = WARDS.includes(p.get('ward')) ? p.get('ward') : '__all__';
  return { date:p.get('date') || '', ward, q:p.get('q') || '' };
}

export function buildCopyUrl(filters){
  const p = new URLSearchParams();
  if(filters.date) p.set('date', filters.date);
  if(filters.ward && filters.ward !== '__all__') p.set('ward', filters.ward);
  if(filters.q) p.set('q', filters.q);
  const qs = p.toString();
  return 'copy.html' + (qs ? '?' + qs : '');
}

export async function loadManifest(){
  const res = await fetch('data/manifest.json',{cache:'no-store'});
  if(!res.ok) throw new Error(`manifest load failed: ${res.status}`);
  return res.json();
}

export async function loadWeekend(manifest,satIso){
  const entry=(manifest.weekends||[]).find(w=>w.sat===satIso);
  if(!entry) return {entry:null,data:null};
  const res=await fetch('data/'+entry.file,{cache:'no-store'});
  if(!res.ok) throw new Error(`weekend load failed: ${res.status}`);
  return {entry,data:await res.json()};
}

export function escapeHtml(value){
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}

export function safeHttpUrl(value){
  try {
    const u = new URL(String(value || ''));
    return (u.protocol === 'http:' || u.protocol === 'https:') ? u.href : '';
  } catch { return ''; }
}
