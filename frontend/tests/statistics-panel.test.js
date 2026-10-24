import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'
import { parseStatistics } from '../src/statistics/statisticsModel.js'

const fixture = (days = 7) => ({ days, timezone: 'Asia/Shanghai', start_date: days === 7 ? '2024-02-24' : '2024-02-01', end_date: '2024-03-01', website_visitors: 0, projects: [{ project_id: 9, name: '', visitors: 0 }, { project_id: 2, name: '下架历史项目', visitors: 12 }] })
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a;reject=b });return {promise,resolve,reject} }
function mount(api, onUnauthenticated = () => {}) {
  const { descriptor } = parse(readFileSync(new URL('../src/admin/StatisticsPanel.vue', import.meta.url), 'utf8'))
  const code = compileScript(descriptor, { id: 'statistics-test', inlineTemplate: true }).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) => 'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace(/^import .*statisticsModel.*$/gm, '')
    .replace('export default', 'return')
  const component = new Function('Vue', 'parseStatistics', code)(Vue, parseStatistics)
  const element = (type, text = '') => ({ type, text, props: {}, children: [], parent: null })
  const renderer = Vue.createRenderer({ createElement: element, createText: text => element('#text', text), createComment: text => element('#comment', text),
    setText(node,text) { node.text=text }, setElementText(node,text) { node.text=text;node.children=[] }, patchProp(node,key,old,value) { node.props[key]=value },
    insert(node,parent,anchor) { if(node.parent)node.parent.children.splice(node.parent.children.indexOf(node),1);const i=anchor?parent.children.indexOf(anchor):-1;parent.children.splice(i<0?parent.children.length:i,0,node);node.parent=parent },
    remove(node) { node.parent.children.splice(node.parent.children.indexOf(node),1) }, parentNode: node=>node.parent, nextSibling: node=>node.parent?.children[node.parent.children.indexOf(node)+1] })
  const root=element('root'),app=renderer.createApp(component,{api,onUnauthenticated});app.mount(root)
  const nodes=()=>{const all=[];const visit=n=>{all.push(n);n.children.forEach(visit)};visit(root);return all}
  return { nodes, text:()=>nodes().map(n=>n.text).join(' '), button:label=>nodes().find(n=>n.type==='button'&&n.text===label), unmount:()=>app.unmount() }
}

test('parser accepts leap-year server dates, real zeros, empty projects and preserves server order with detached data', () => {
  const raw=fixture();raw.extra='private';raw.projects[0].extra='private'
  const parsed=parseStatistics(raw,7)
  assert.deepEqual(parsed,fixture());assert.notEqual(parsed,raw);assert.notEqual(parsed.projects,raw.projects);assert.notEqual(parsed.projects[0],raw.projects[0])
  raw.projects[0].name='changed';assert.equal(parsed.projects[0].name,'')
  assert.deepEqual(parseStatistics({...fixture(30),projects:[]},30).projects,[])
})

const invalid = [null, [], {}, ...[
  {days:30}, {days:'7'}, {timezone:'UTC'}, {start_date:'2023-02-29'}, {start_date:'2024-02-30'}, {start_date:'2024-2-24'}, {start_date:'0000-02-24'}, {end_date:'2024-02-23'}, {end_date:'2024-03-02'},
  {website_visitors:-1}, {website_visitors:1.5}, {website_visitors:Number.MAX_SAFE_INTEGER+1}, {website_visitors:'0'}, {projects:null}, {projects:new Array(1)}, {projects:[Object.assign([], {project_id:1,name:'x',visitors:0})]},
  ...[0,-1,1.5,Number.MAX_SAFE_INTEGER+1,'9'].map(project_id=>({projects:[{project_id,name:'x',visitors:0}]})),
  ...[-1,1.5,Number.MAX_SAFE_INTEGER+1,'0',NaN,Infinity].map(visitors=>({projects:[{project_id:1,name:'x',visitors}]})),
  {projects:[{project_id:1,name:null,visitors:0}]}, {projects:[null]}, {projects:[{project_id:1,name:'a',visitors:0},{project_id:1,name:'b',visitors:0}]},
].map(change=>({...fixture(),...change}))]
for (const [index,value] of invalid.entries()) test(`parser rejects malformed response ${index} rather than manufacturing zeros`,()=>assert.throws(()=>parseStatistics(value,7)))
for (const days of [undefined,null,0,7.5,'7',14,Infinity]) test(`parser rejects unsupported expected window ${days}`,()=>assert.throws(()=>parseStatistics(fixture(),days)))

test('real panel loads 7 days, displays true zero, historical projects and server interval, then 30 days empty state', async()=>{
  const calls=[];const page=mount({load:async days=>{calls.push(days);return days===7?fixture():{...fixture(30),projects:[]}}})
  try {
    assert.equal(page.nodes().some(n=>n.type==='table'),false)
    await flush();assert.deepEqual(calls,[7]);assert.match(page.text(),/2024-02-24.*2024-03-01/);assert.match(page.text(),/北京时间/)
    assert.match(page.text(),/未命名项目 #9/);assert.match(page.text(),/下架历史项目/);assert.match(page.text(),/整个区间/);assert.match(page.text(),/管理员/);assert.match(page.text(),/预览/)
    assert.equal(page.nodes().find(n=>n.props.class==='statistics-count').text,'0')
    await page.button('近30天').props.onClick();await flush();assert.deepEqual(calls,[7,30]);assert.match(page.text(),/暂无项目/)
  } finally {page.unmount()}
})

for (const oldResult of ['success','503','401']) test(`switch clears old interval and ignores stale ${oldResult} including loading and auth effects`,async()=>{
  const pending=[];let events=0
  const page=mount({load:days=>{const request=deferred();pending.push({days,...request});return request.promise}},()=>events++)
  try {
    pending[0].resolve(fixture());await flush()
    page.button('刷新').props.onClick();await Vue.nextTick()
    page.button('近30天').props.onClick();await Vue.nextTick()
    assert.equal(page.nodes().some(n=>n.type==='table'),false);assert.doesNotMatch(page.text(),/2024-02-24/)
    if(oldResult==='success')pending[1].resolve(fixture());else pending[1].reject({status:Number(oldResult)})
    await flush();assert.equal(events,0);assert.match(page.text(),/正在加载/);assert.equal(page.nodes().some(n=>n.type==='table'),false)
    pending[2].resolve({...fixture(30),website_visitors:21});await flush()
    assert.match(page.text(),/2024-02-01/);assert.equal(page.nodes().find(n=>n.props.class==='statistics-count').text,'21')
  } finally {page.unmount()}
})

test('rapid 7/30/7 selection accepts only latest success and ignores late rejection after success',async()=>{
  const pending=[];let events=0;const page=mount({load:()=>{const r=deferred();pending.push(r);return r.promise}},()=>events++)
  try {
    page.button('近30天').props.onClick();await Vue.nextTick();page.button('近7天').props.onClick();await Vue.nextTick()
    pending[2].resolve({...fixture(),website_visitors:77});await flush()
    pending[0].resolve({...fixture(),website_visitors:99});pending[1].reject({status:401});await flush()
    assert.equal(page.nodes().find(n=>n.props.class==='statistics-count').text,'77');assert.equal(events,0);assert.doesNotMatch(page.text(),/正在加载|失效/)
  } finally {page.unmount()}
})

for (const status of [403,503,0,'invalid']) test(`current ${status} response shows safe retry without zero or raw errors`,async()=>{
  let fail=true;const page=mount({load:async()=>{if(fail){if(status==='invalid')return {};throw Object.assign(new Error('private-server-text'),{status})}return fixture()}})
  try {
    await flush();assert.ok(page.nodes().find(n=>n.props.role==='alert'));assert.doesNotMatch(page.text(),/private-server-text/);assert.equal(page.nodes().some(n=>n.props.class==='statistics-count'),false)
    fail=false;await page.button('重试加载').props.onClick();await flush();assert.equal(page.nodes().find(n=>n.props.class==='statistics-count').text,'0')
  } finally {page.unmount()}
})

test('current 401 uses common unauthenticated callback',async()=>{
  let events=0;const page=mount({load:async()=>{throw {status:401}}},()=>events++)
  try {await flush();assert.equal(events,1);assert.equal(page.nodes().some(n=>n.type==='table'),false)}finally{page.unmount()}
})
for (const outcome of ['success','401','503']) test(`unmount ignores late ${outcome}`,async()=>{
  const request=deferred();let events=0;const page=mount({load:()=>request.promise},()=>events++);page.unmount()
  if(outcome==='success')request.resolve(fixture());else request.reject({status:Number(outcome)})
  await flush();assert.equal(events,0);assert.equal(page.text(),'')
})
