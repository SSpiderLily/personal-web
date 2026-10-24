import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'

const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
globalThis.Document ??= class Document {}
globalThis.ShadowRoot ??= class ShadowRoot {}
function mount(path, props, realUpload = false) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  const code = compileScript(descriptor, { id: 'tools-test', inlineTemplate: true }).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) => 'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace('export default', 'return')
  const imageDescriptor = parse(readFileSync(new URL('../src/admin/ImageUpload.vue', import.meta.url), 'utf8')).descriptor
  const imageSource = compileScript(imageDescriptor, {id:'profile-upload-test', inlineTemplate:true}).content.replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) => 'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue').replace('export default', 'return')
  const actualImageUpload = new Function('Vue', imageSource)(Vue)
  const component = new Function('Vue', 'ImageUpload', code.replace(/import ImageUpload[^\n]+/, ''))(Vue, realUpload ? actualImageUpload : { props: ['api', 'modelValue'], emits: ['update:modelValue'], setup: (props, {emit}) => () => Vue.h('button', { 'aria-label': '模拟上传', onClick: async () => emit('update:modelValue', await props.api.upload({name:'avatar.png'})) }, '上传') })
  const element = (type, text = '') => ({ type, text, props: {}, children: [], parent: null, events: {}, getRootNode() { return {} }, addEventListener(name, handler) { this.events[name] = handler } })
  const renderer = Vue.createRenderer({ createElement: element, createText: text => element('#text', text), createComment: text => element('#comment', text),
    setText(node,text) { node.text=text }, setElementText(node,text) { node.text=text; node.children=[] }, patchProp(node,key,old,value) { node.props[key]=value },
    insert(node,parent,anchor) { if(node.parent) node.parent.children.splice(node.parent.children.indexOf(node),1); const i=anchor?parent.children.indexOf(anchor):-1; parent.children.splice(i<0?parent.children.length:i,0,node); node.parent=parent },
    remove(node) { node.parent.children.splice(node.parent.children.indexOf(node),1) }, parentNode: node=>node.parent, nextSibling: node=>node.parent?.children[node.parent.children.indexOf(node)+1] })
  const root=element('root'), app=renderer.createApp(component,props); const instance=app.mount(root)
  const nodes = () => { const all=[]; const visit=n=>{all.push(n);n.children.forEach(visit)};visit(root);return all }
  return { instance, render: () => app._instance.update(), nodes, text: () => nodes().map(n=>n.text).join(' '), unmount:()=>app.unmount() }
}
const button = (page,label) => page.nodes().find(n=>n.type==='button'&&n.text===label)


const profile = () => ({ name: '', title: '', introduction: '', skills: [], avatar_file_id: null, contacts: [], social_links: [], projects: [] })
const field = (page, label) => page.nodes().find(n => n.props['aria-label'] === label)
const edit = (page,label,value) => { const node=field(page,label); node.value=value; node.events.input({target:node}) }

test('ProfilePanel retains draft on failures and retry saves exact editable fields', async () => {
  let fail=true, supplied
  const page=mount('../src/admin/ProfilePanel.vue',{api:{load:async()=>profile(),save:async value=>{supplied=structuredClone(value);if(fail)throw {status:503};return value}}})
  try {
    await flush(); edit(page,'姓名','草稿'); await Vue.nextTick()
    await button(page,'保存资料').props.onClick({preventDefault(){}});await flush()
    assert.equal(field(page,'姓名').value,'草稿');assert.match(page.text(),/暂时不可用/)
    fail=false;await button(page,'保存资料').props.onClick({preventDefault(){}});await flush()
    assert.equal(supplied.name,'草稿');assert.equal('projects' in supplied,false);assert.match(page.text(),/已保存/)
  } finally {page.unmount()}
})

test('ProfilePanel clears private draft and emits on authentication loss', async () => {
  let events=0
  const page=mount('../src/admin/ProfilePanel.vue',{api:{load:async()=>profile(),save:async()=>{throw {status:401}}},onUnauthenticated:()=>events++})
  try {
    await flush();edit(page,'姓名','私密草稿');await Vue.nextTick();await button(page,'保存资料').props.onClick({preventDefault(){}});await flush()
    assert.equal(events,1);assert.equal(field(page,'姓名'),undefined);assert.doesNotMatch(page.text(),/私密草稿/)
  } finally {page.unmount()}
})

test('PublicProfile hides empty identity and uses only controlled avatar URLs', () => {
  const empty=mount('../src/components/PublicProfile.vue',{profile:profile()})
  try {assert.equal(empty.nodes().filter(n=>['h1','img','a'].includes(n.type)).length,0)}finally{empty.unmount()}
  const page=mount('../src/components/PublicProfile.vue',{profile:{...profile(),name:'真实姓名',avatar_file_id:'d14b633a-e3b7-4bcc-9dc7-1a87326e74bd',introduction:'<script>x</script>',contacts:[{label:'危险',url:'javascript:alert(1)'},{label:'邮箱',url:'mailto:a@example.com'}]}})
  try {
    assert.equal(page.nodes().find(n=>n.type==='img').props.src,'/api/files/d14b633a-e3b7-4bcc-9dc7-1a87326e74bd')
    assert.equal(page.nodes().filter(n=>n.type==='a').length,1)
    assert.match(page.text(),/<script>x<\/script>/)
  }finally{page.unmount()}
})


test('ProfilePanel focus recheck preserves draft and authentication failures clear it', async () => {
  let mode='ok', events=0
  const page=mount('../src/admin/ProfilePanel.vue',{api:{load:async()=>{if(mode==='failed')throw {status:503};if(mode==='expired')throw {status:401};return {...profile(),name:'服务器'};}},onUnauthenticated:()=>events++})
  try {
    await flush();edit(page,'姓名','本地草稿');await Vue.nextTick()
    await page.instance.revalidate();await flush();assert.equal(field(page,'姓名').value,'本地草稿')
    mode='failed';await page.instance.revalidate();await flush();assert.equal(field(page,'姓名').value,'本地草稿')
    mode='expired';await page.instance.revalidate();await flush();assert.equal(events,1);assert.equal(field(page,'姓名'),undefined)
  }finally{page.unmount()}
})

test('ProfilePanel waits for avatar upload before allowing save', async () => {
  let resolveUpload,saved=0
  const page=mount('../src/admin/ProfilePanel.vue',{api:{load:async()=>profile(),upload:()=>new Promise(resolve=>{resolveUpload=resolve}),save:async value=>{saved++;return value}}})
  try {
    await flush();edit(page,'姓名','草稿');await Vue.nextTick()
    const pending=field(page,'模拟上传').props.onClick();await Vue.nextTick()
    await button(page,'保存资料').props.onClick({preventDefault(){}});await flush();assert.equal(saved,0)
    resolveUpload({id:'d14b633a-e3b7-4bcc-9dc7-1a87326e74bd'});await pending;await flush()
    await button(page,'保存资料').props.onClick({preventDefault(){}});await flush();assert.equal(saved,1)
  }finally{page.unmount()}
})


test('ProfilePanel preserves Enter and second skill across real input updates until save', async () => {
  let fail=true, supplied
  const page=mount('../src/admin/ProfilePanel.vue',{api:{load:async()=>profile(),save:async value=>{supplied=structuredClone(value);if(fail)throw {status:503};return value}}})
  try {
    await flush();edit(page,'技能','Python');await Vue.nextTick()
    edit(page,'技能',field(page,'技能').value+'\n');await Vue.nextTick();page.render();await Vue.nextTick()
    assert.equal(field(page,'技能').value,'Python\n')
    edit(page,'技能',field(page,'技能').value+' Vue ');await Vue.nextTick()
    edit(page,'技能',field(page,'技能').value+'\n\n');await Vue.nextTick()
    assert.equal(field(page,'技能').value,'Python\n Vue \n\n')
    await button(page,'保存资料').props.onClick({preventDefault(){}});await flush()
    assert.deepEqual(supplied.skills,['Python','Vue'])
    assert.equal(field(page,'技能').value,'Python\n Vue \n\n')
    fail=false;await button(page,'保存资料').props.onClick({preventDefault(){}});await flush()
    assert.equal(field(page,'技能').value,'Python\nVue')
    edit(page,'技能','更改\n');await Vue.nextTick();button(page,'撤销更改').props.onClick();await Vue.nextTick()
    assert.equal(field(page,'技能').value,'Python\nVue')
  }finally{page.unmount()}
})

test('ProfilePanel existing avatar has controlled preview and uploaded avatar retains metadata', async () => {
  const identifier='d14b633a-e3b7-4bcc-9dc7-1a87326e74bd'
  const uploaded='769c407e-d505-4ccc-ab28-7ec8edb2d7b4'
  const page=mount('../src/admin/ProfilePanel.vue',{api:{load:async()=>({...profile(),avatar_file_id:identifier}),upload:async()=>({id:uploaded,url:'https://untrusted.test/image.png',width:3,height:2,byte_size:50})}},true)
  try {
    await flush()
    assert.equal(page.nodes().find(n=>n.type==='img').props.src,`/api/admin/files/${identifier}`)
    assert.equal(page.nodes().filter(n=>n.type==='figcaption').length,0)
    const input=page.nodes().find(n=>n.type==='input'&&n.props.type==='file')
    await input.props.onChange({target:{files:[{name:'avatar.png',type:'image/png',size:50}],value:'selected'}});await flush()
    assert.equal(page.nodes().filter(n=>n.type==='img').length,1)
    assert.equal(page.nodes().find(n=>n.type==='img').props.src,`/api/admin/files/${uploaded}`)
    assert.equal(page.nodes().find(n=>n.type==='figcaption').text,'3 × 2 · 50 字节')
    button(page,'移除头像').props.onClick();await Vue.nextTick()
    assert.equal(page.nodes().filter(n=>n.type==='img').length,0)
  }finally{page.unmount()}
})
