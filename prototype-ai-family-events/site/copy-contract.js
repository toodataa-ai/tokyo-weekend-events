export const COPY_CONTRACT_VERSION = '1.0';

export const COPY_FIELD_KEYS = [
  'title','venue','datetime','price','description','official','source','image'
];

export function copyValues(ev){
  const title = ev?.name || ev?.url || '';
  const venue = ev?.venue || ev?.ward || '';
  const datetime = (ev?.period || '') + (ev?.time ? '　' + ev.time : '');
  const price = ev?.price || '（料金情報は公式サイトでご確認ください）';
  const description = ev?.description || '';
  const official = ev?.official_url || ev?.url || '';
  const source = ev?.source || '';
  const image = ev?.image || '';
  return {title,venue,datetime,price,description,official,source,image};
}

export function copyFieldList(ev){
  const v = copyValues(ev);
  const fields = [
    {key:'title', label:'タイトル', value:v.title},
    {key:'venue', label:'📍 場所', value:v.venue},
    {key:'datetime', label:'🗓 日時', value:v.datetime},
    {key:'price', label:'💰 料金', value:v.price},
    {key:'description', label:'📝 説明', value:v.description},
    {key:'official', label:'🔗 公式サイト', value:v.official, isLink:true},
    {key:'source', label:'📌 情報元サイト', value:v.source, isLink:true}
  ];
  if(v.image) fields.push({key:'image', label:'🖼 サムネイル画像URL', value:v.image, isLink:true});
  return fields;
}

export function copyAllText(ev){
  return copyFieldList(ev).map(f => f.value).join('\n');
}
