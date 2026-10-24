import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'

const defaults = () => ({ tools: [...Array.from({ length: 9 }, (_, i) => ({ tool_key: `grid_0${i+1}`, placement: 'grid', is_visible: true, sort_order: i })), { tool_key: 'dice', placement: 'floating', is_visible: true, sort_order: 0 }] })
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
function mount(path, props) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  const code = compileScript(descriptor, { id: 'tools-test', inlineTemplate: true }).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) => 'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace('export default', 'return')
  const component = new Function('Vue', code)(Vue)
  const element = (type, text = '') => ({ type, text, props: {}, children: [], parent: null, events: {}, addEventListener(name, handler) { this.events[name] = handler } })
  const renderer = Vue.createRenderer({ createElement: element, createText: text => element('#text', text), createComment: text => element('#comment', text),
    setText(node,text) { node.text=text }, setElementText(node,text) { node.text=text; node.children=[] }, patchProp(node,key,old,value) { node.props[key]=value },
    insert(node,parent,anchor) { if(node.parent) node.parent.children.splice(node.parent.children.indexOf(node),1); const i=anchor?parent.children.indexOf(anchor):-1; parent.children.splice(i<0?parent.children.length:i,0,node); node.parent=parent },
    remove(node) { node.parent.children.splice(node.parent.children.indexOf(node),1) }, parentNode: node=>node.parent, nextSibling: node=>node.parent?.children[node.parent.children.indexOf(node)+1] })
  const root=element('root'), app=renderer.createApp(component,props); app.mount(root)
  const nodes = () => { const all=[]; const visit=n=>{all.push(n);n.children.forEach(visit)};visit(root);return all }
  return { nodes, text: () => nodes().map(n=>n.text).join(' '), unmount:()=>app.unmount() }
}
const button = (page,label) => page.nodes().find(n=>n.type==='button'&&n.text===label)
const toggle = (node, checked) => { node.checked = checked; node.events.change({ target: node }) }
const checkbox = (page,key) => page.nodes().find(n=>n.type==='input'&&n.props['aria-label']===`${key} 显示`)

test('ToolGrid preserves key-bound icons when reordered or hidden', () => {
  const items = [defaults().tools[7],defaults().tools[1]]
  const page=mount('../src/components/ToolGrid.vue',{items})
  try {
    const cells=page.nodes().filter(n=>n.type==='li')
    assert.equal(cells.length,2)
    assert.match(cells[0].props['aria-label'],/8/)
    assert.equal(page.nodes().filter(n=>n.type==='circle')[0].props.cx,'10')
    assert.equal(page.nodes().filter(n=>n.type==='path')[0].props.d,'m15 15 6 6M7 10h6M10 7v6')
  } finally {page.unmount()}
})

test('ToolsPanel saves full draft, moves order, and resets to latest successful baseline', async () => {
  let supplied
  const page=mount('../src/admin/ToolsPanel.vue',{api:{load:async()=>defaults(),save:async payload=>{supplied=structuredClone(payload);return payload}}})
  try {
    await flush()
    toggle(checkbox(page,'grid_01'),false)
    page.nodes().find(n=>n.type==='button'&&n.props['aria-label']==='grid_02 上移').props.onClick()
    await Vue.nextTick()
    await button(page,'保存设置').props.onClick()
    await flush()
    assert.equal(supplied.tools.length,10)
    assert.equal(supplied.tools.find(t=>t.tool_key==='grid_01').is_visible,false)
    assert.equal(supplied.tools.find(t=>t.tool_key==='grid_02').sort_order,0)
    toggle(checkbox(page,'grid_01'),true)
    await Vue.nextTick()
    button(page,'撤销更改').props.onClick()
    await Vue.nextTick()
    assert.equal(checkbox(page,'grid_01').checked,false)
    assert.match(page.text(),/已保存/)
  } finally {page.unmount()}
})

test('ToolsPanel keeps draft after safe errors and emits unauthenticated for 401', async () => {
  let expired=false,events=0
  const page=mount('../src/admin/ToolsPanel.vue',{api:{load:async()=>defaults(),save:async()=>{throw Object.assign(new Error('private-driver-detail'),{status:expired?401:503})}},onUnauthenticated:()=>events++})
  try {
    await flush(); toggle(checkbox(page,'dice'),false); await Vue.nextTick()
    await button(page,'保存设置').props.onClick(); await flush()
    assert.equal(checkbox(page,'dice').checked,false)
    assert.doesNotMatch(page.text(),/private-driver-detail/)
    expired=true; await button(page,'保存设置').props.onClick(); await flush()
    assert.equal(events,1)
    assert.equal(checkbox(page,'dice').checked,false)
  } finally {page.unmount()}
})

test('ToolsPanel retries load failure and guards duplicate save while pending', async () => {
  let failed=true,resolveSave,calls=0
  const page=mount('../src/admin/ToolsPanel.vue',{api:{load:async()=>{if(failed)throw new Error('secret');return defaults()},save:()=>{calls++;return new Promise(resolve=>{resolveSave=resolve})}}})
  try {
    await flush(); assert.doesNotMatch(page.text(),/secret/);failed=false
    await button(page,'重试加载').props.onClick();await flush()
    toggle(checkbox(page,'dice'),false);await Vue.nextTick()
    const save=button(page,'保存设置').props.onClick
    const pending=save();await save();assert.equal(calls,1)
    resolveSave(defaults());await pending;await flush()
    assert.equal(checkbox(page,'dice').checked,true)
  } finally {page.unmount()}
})

test('ToolsPanel load 401 emits authentication loss and malformed success retains draft', async () => {
  let events = 0
  const expired = mount('../src/admin/ToolsPanel.vue', { api: { load: async () => { throw { status: 401 } } }, onUnauthenticated: () => events++ })
  try {
    await flush()
    assert.equal(events, 1)
    assert.equal(checkbox(expired, 'dice'), undefined)
  } finally { expired.unmount() }
  const page = mount('../src/admin/ToolsPanel.vue', { api: { load: async () => defaults(), save: async () => ({ tools: [] }) } })
  try {
    await flush()
    toggle(checkbox(page, 'dice'), false)
    await Vue.nextTick()
    await button(page, '保存设置').props.onClick()
    await flush()
    assert.equal(checkbox(page, 'dice').checked, false)
    assert.match(page.text(), /暂时不可用/)
    assert.equal(button(page, '保存设置').props.disabled, false)
  } finally { page.unmount() }
})
