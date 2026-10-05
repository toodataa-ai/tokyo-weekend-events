import assert from 'node:assert/strict';
import {COPY_CONTRACT_VERSION,COPY_FIELD_KEYS,copyValues,copyFieldList,copyAllText} from '../site/copy-contract.js';

assert.equal(COPY_CONTRACT_VERSION,'1.0');
assert.deepEqual(COPY_FIELD_KEYS,[
  'title','venue','datetime','price','description','official','source','image'
]);

const full = {
  name:'テストイベント', url:'https://example.com/base', ward:'中野区', venue:'中野サンプル会場',
  period:'10/10〜10/11', time:'10:00〜16:00', price:'無料', description:'説明本文',
  official_url:'https://example.com/official', source:'https://example.com/source', image:'https://example.com/image.jpg'
};

assert.deepEqual(copyFieldList(full).map(x=>x.key),COPY_FIELD_KEYS);
assert.equal(copyAllText(full),[
  'テストイベント','中野サンプル会場','10/10〜10/11　10:00〜16:00','無料','説明本文',
  'https://example.com/official','https://example.com/source','https://example.com/image.jpg'
].join('\n'));

const fallback = {url:'https://example.com/e',ward:'杉並区',period:'10/10'};
const fv = copyValues(fallback);
assert.equal(fv.title,'https://example.com/e');
assert.equal(fv.venue,'杉並区');
assert.equal(fv.datetime,'10/10');
assert.equal(fv.price,'（料金情報は公式サイトでご確認ください）');
assert.equal(fv.official,'https://example.com/e');
assert.equal(fv.source,'');
assert.equal(fv.image,'');
assert.deepEqual(copyFieldList(fallback).map(x=>x.key),[
  'title','venue','datetime','price','description','official','source'
]);

console.log('copy contract v1: OK');
