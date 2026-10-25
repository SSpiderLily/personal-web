import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as Helpers from '../src/projects/projectContent.js'

const image = '11111111-1111-1111-1111-111111111111'
const value = () => ({id:1,name:'旅行助手',summary:'简介',category:'工具',tech_stack:['Vue'],features:[],cover_file_id:image,cover_alt:'封面',demo_url:'/trip/',source_url:null,blocks:[{kind:'text',body:'原详情'}],screenshots:[],status:'draft',sort_order:0,published_at:null,updated_at:'2026-10-24T00:00:00Z'})
const flush = async()=>{await new Promise(resolve=>setImmediate(resolve));await Vue.nextTick()}
function mount(api) {
  const {descriptor}=parse(readFileSync(new URL('../src/admin/ProjectsPanel.vue',import.meta.url),'utf8'))
  let code=compileScript(descriptor,{id:'projects-test'}).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g,(_,names)=>'const {'+names.replace(/(\w+) as (\w+)/g,'$1: $2')+'}=Vue')
    .replace(/import \{([^}]+)\} from ['"][^'"]+projectContent.js['"]/g,(_,names)=>'const {'+names+'}=Helpers')
    .replace(/import (ImageUpload|ProjectContent) from [^\n]+/g,'const $1 = {}')
    .replace('export default','return')
  const component=new Function('Vue','Helpers',code)(Vue,Helpers)
  let state,events=[],exposed
  const wrapper={props:['api'],setup(props,ctx){state=component.setup(props,{...ctx,expose:val=>{exposed=val},emit:(...args)=>events.push(args)});return()=>Vue.h('div')}}
  const renderer=Vue.createRenderer({createElement:()=>({}),insert(){},remove(){},patchProp(){},createText:()=>({}),createComment:()=>({}),setText(){},setElementText(){},parentNode(){},nextSibling(){}})
  const app=renderer.createApp(wrapper,{api});app.mount({})
  return {get state(){return state},events,get exposed(){return exposed},unmount:()=>app.unmount()}
}

test('project images and links use controlled URLs including development trip rule',()=>{
  assert.equal(Helpers.projectImageUrl(image),'/api/files/'+image)
  assert.equal(Helpers.projectImageUrl(image,true),'/api/admin/files/'+image)
  assert.equal(Helpers.projectImageUrl('https://evil.example'),null)
  assert.equal(Helpers.projectLink('/trip/',{DEV:true}), 'http://127.0.0.1:5173/')
  assert.equal(Helpers.projectLink('/trip/',{DEV:false}), '/trip/')
  assert.equal(Helpers.projectLink('/trip/',{VITE_TRIP_DEMO_URL:'https://demo.example/trip/'}), 'https://demo.example/trip/')
  for(const url of ['javascript:alert(1)','//evil.example','https://a:b@example.com','https://example.com\\bad','https://example.com/%0a']) assert.equal(Helpers.projectLink(url),null)
})

test('memory preview does not save; failed save keeps draft and retry sends complete editable object',async()=>{
  let fail=true,calls=0,received
  const page=mount({list:async()=>({projects:[value()]}),get:async()=>({project:value()}),save:async(id,payload)=>{calls++;received=structuredClone(payload);if(fail)throw {status:503};return {project:{...value(),...payload}}}})
  try{
    await flush();await page.state.selectProject(1);page.state.draft.value.name='编辑中'
    page.state.preview.value=true;await flush();assert.equal(calls,0)
    await page.state.save();assert.equal(page.state.draft.value.name,'编辑中');assert.equal(page.state.dirty.value,true)
    fail=false;await page.state.save();assert.equal(received.name,'编辑中');assert.equal('status' in received,false);assert.equal('id' in received,false)
    assert.equal(page.state.dirty.value,false)
  }finally{page.unmount()}
})

test('401 clears project draft and emits unauthenticated, transient loads retain it',async()=>{
  let status=503
  const page=mount({list:async()=>({projects:[value()]}),get:async()=>({project:value()}),save:async()=>{throw {status}}})
  try{
    await flush();await page.state.selectProject(1);page.state.draft.value.summary='未保存'
    await page.state.save();assert.equal(page.state.draft.value.summary,'未保存')
    status=401;await page.state.save();assert.equal(page.state.draft.value,null);assert.ok(page.events.some(e=>e[0]==='unauthenticated'))
  }finally{page.unmount()}
})

test('switch requires explicit discard, reorder and publish require saved draft',async()=>{
  let published=0,orders=[]
  const page=mount({list:async()=>({projects:[value(),{...value(),id:2}]}),get:async id=>({project:{...value(),id}}),publish:async()=>{published++;return{project:{...value(),status:'published'}}},reorder:async ids=>{orders=ids;return{projects:ids.map((id,sort_order)=>({...value(),id,sort_order}))}}})
  try{
    await flush();await page.state.selectProject(1);page.state.draft.value.name='未保存'
    await page.state.selectProject(2);assert.equal(page.state.selectedId.value,1);assert.equal(page.state.pendingSelection.value,2)
    await page.state.publish();assert.equal(published,0)
    await page.state.confirmSelection();assert.equal(page.state.selectedId.value,2)
    await page.state.moveProject(2,-1);assert.deepEqual(orders,[2,1])
    await page.state.publish();assert.equal(published,1)
  }finally{page.unmount()}
})

test('block and screenshot ordering changes draft only and upload binds identifier',async()=>{
  const page=mount({list:async()=>({projects:[]})})
  try{
    await flush();await page.state.selectProject(null)
    page.state.addText();page.state.draft.value.blocks[0].body='甲';page.state.addText();page.state.draft.value.blocks[1].body='乙'
    page.state.moveItem(page.state.draft.value.blocks,1,-1);assert.equal(page.state.draft.value.blocks[0].body,'乙')
    page.state.addImage({id:image},'blocks');page.state.addImage({id:image},'screenshots')
    assert.equal(page.state.draft.value.blocks[2].file_id,image);assert.equal(page.state.draft.value.screenshots[0].file_id,image)
    page.state.setCover({id:image});assert.equal(page.state.draft.value.cover_file_id,image)
  }finally{page.unmount()}
})

test('shared ProjectContent renders ordered plain text and private/public image routes without writing',async()=>{
  const {descriptor}=parse(readFileSync(new URL('../src/components/ProjectContent.vue',import.meta.url),'utf8'))
  const code=compileScript(descriptor,{id:'project-render',inlineTemplate:true}).content
    .replace(/import \{([^}]+)\} from ["']vue["']/g,(_,names)=>'const {'+names.replace(/(\w+) as (\w+)/g,'$1: $2')+'}=Vue')
    .replace(/import \{([^}]+)\} from ['"][^'"]+projectContent.js['"]/g,(_,names)=>'const {'+names+'}=Helpers')
    .replace('export default','return')
  const component=new Function('Vue','Helpers',code)(Vue,Helpers)
  const element=(type,text='')=>({type,text,props:{},children:[],parent:null})
  const renderer=Vue.createRenderer({createElement:element,createText:text=>element('#text',text),createComment:text=>element('#comment',text),
    insert(node,parent){parent.children.push(node);node.parent=parent},remove(){},patchProp(node,key,old,value){node.props[key]=value},setText(node,text){node.text=text},setElementText(node,text){node.text=text},parentNode:node=>node.parent,nextSibling(){}})
  for(const privateImages of [false,true]){
    const root=element('root'),project={...value(),blocks:[{kind:'text',body:'<script>危险字符串</script>'},{kind:'image',file_id:image,caption:'第二块'}],source_url:'javascript:alert(1)'}
    const app=renderer.createApp(component,{project,privateImages});app.mount(root)
    const nodes=[];function visit(node){nodes.push(node);node.children.forEach(visit)}visit(root)
    assert.equal(nodes.filter(node=>node.type==='img').every(node=>node.props.src===`/api/${privateImages?'admin/':''}files/${image}`),true)
    assert.equal(nodes.some(node=>node.type==='script'),false)
    assert.equal(nodes.some(node=>node.text==='<script>危险字符串</script>'),true)
    assert.equal(nodes.filter(node=>node.type==='a').some(node=>node.props.href.startsWith('javascript:')),false)
    assert.equal(nodes.find(node=>node.type==='a').props.rel,'noopener noreferrer')
    app.unmount()
  }
})

test('editor full template compiles using the same Vue compiler as production',()=>{
  const {descriptor}=parse(readFileSync(new URL('../src/admin/ProjectsPanel.vue',import.meta.url),'utf8'))
  assert.ok(compileScript(descriptor,{id:'project-editor',inlineTemplate:true}).content.includes('项目草稿预览'))
})

test('malformed success preserves baseline and duplicate saves are guarded',async()=>{
  let resolve,calls=0
  const page=mount({list:async()=>({projects:[value()]}),get:async()=>({project:value()}),save:()=>{calls++;return new Promise(done=>{resolve=done})}})
  try{
    await flush();await page.state.selectProject(1);page.state.draft.value.name='保留'
    const pending=page.state.save();await page.state.save();assert.equal(calls,1)
    resolve({project:{id:1}});await pending;assert.equal(page.state.draft.value.name,'保留');assert.equal(page.state.dirty.value,true)
  }finally{page.unmount()}
})

test('in-flight uploads guard save, publication, ordering and selection until the image can bind',async()=>{
  let finishUpload,saved=0,published=0,reordered=0
  const page=mount({list:async()=>({projects:[value(),{...value(),id:2}]}),get:async()=>({project:value()}),upload:()=>new Promise(resolve=>{finishUpload=resolve}),save:async()=>{saved++;return{project:value()}},publish:async()=>{published++;return{project:value()}},reorder:async()=>{reordered++;return{projects:[]}}})
  try{
    await flush();await page.state.selectProject(1)
    const uploading=page.state.uploadApi.upload({name:'test.png'})
    await page.state.save();await page.state.publish();await page.state.moveProject(1,1);await page.state.selectProject(null)
    assert.equal(saved,0);assert.equal(published,0);assert.equal(reordered,0);assert.equal(page.state.selectedId.value,1)
    finishUpload({id:image});page.state.setCover(await uploading)
    assert.equal(page.state.uploading.value,0);assert.equal(page.state.draft.value.cover_file_id,image)
  }finally{page.unmount()}
})

test('backend accepted codepoint limits and safe encoded URLs roundtrip through parseProject',()=>{
  const project={...value(),name:'😀'.repeat(100),summary:'😀'.repeat(2000),category:'😀'.repeat(100),cover_alt:'😀'.repeat(500),tech_stack:['😀'.repeat(100)],features:['😀'.repeat(500)],blocks:[{kind:'text',body:'😀'.repeat(10000)}]}
  for(const demo_url of ['https://example.com/100%25','https://example.com/%F0%9F%98%80','https://example.com/😀','http://localhost:5173/','http://127.0.0.1:5173/','https://[::1]/']){
    assert.deepEqual(Helpers.parseProject({...project,demo_url}).name,project.name)
  }
  assert.throws(()=>Helpers.parseProject({...project,name:'😀'.repeat(101)}))
  for(const url of ['https://example.com/100%','https://example.com/%FF','https://%','https://example.com/%E0%A4','https://bad_host.example/','https://example.123/','https://127.1/','https://example.com/%ED%A0%80']) assert.equal(Helpers.projectLink(url),null,url)
})

test('real Python validation output roundtrips into frontend parsing for Unicode and URL corpus',async()=>{
  const {execFileSync}=await import('node:child_process')
  const backend=new URL('../../backend/',import.meta.url)
  const python=new URL('.venv/bin/python',backend)
  const script=`import json\nfrom app.projects import validate_project\nbase=dict(name='😀'*100,summary='😀'*2000,category='😀'*100,tech_stack=['😀'*100],features=['😀'*500],cover_file_id=None,cover_alt='😀'*500,demo_url=None,source_url=None,blocks=[dict(kind='text',body='😀'*10000)],screenshots=[])\nurls=['https://example.com/100%25','https://example.com/%F0%9F%98%80','https://example.com/😀','http://localhost:5173/','http://127.0.0.1:5173/','https://[::1]/']\njson.dump([validate_project(base | dict(demo_url=url)) for url in urls],__import__('sys').stdout)`
  const {fileURLToPath}=await import('node:url')
  const payloads=JSON.parse(execFileSync(fileURLToPath(python),['-c',script],{cwd:fileURLToPath(backend),encoding:'utf8',maxBuffer:4*1024*1024}))
  for(const payload of payloads) assert.equal(Helpers.parseProject({...value(),...payload}).name,'😀'.repeat(100))
})
