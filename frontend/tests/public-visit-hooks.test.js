import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'

const flush=async()=>{await new Promise(resolve=>setImmediate(resolve));await Vue.nextTick()}
function mountPublic({path='/',project=async id=>({id}),failContent=false}={}) {
 const previous={window:globalThis.window,document:globalThis.document,fetch:globalThis.fetch}
 const window=new EventTarget();window.location={pathname:path};globalThis.window=window
 globalThis.document={body:{style:{overflow:''}}}
 globalThis.fetch=async()=>{if(failContent)throw new Error('offline');return {ok:true,json:async()=>({name:'',title:'',introduction:'',skills:[]})}}
 const calls=[]
 const collector={website:async()=>{calls.push('website');return true},project:async id=>{calls.push(['project',id]);return true},dispose:()=>calls.push('dispose')}
 const descriptor=parse(readFileSync(new URL('../src/App.vue',import.meta.url),'utf8')).descriptor
 const script=compileScript(descriptor,{id:'public-visits',inlineTemplate:false}).content
  .replace(/import \{([^}]+)\} from ['"]vue['"]/g,(_,names)=>'const {'+names.replace(/(\w+) as (\w+)/g,'$1: $2')+'}=Vue')
  .replace(/^import .*$/gm,'').replace('export default','return')
 const component=new Function('Vue','createVisitCollector','usePublicTools','fetchProjects','fetchProject','ProjectContent','PublicProfile','DiceGame','ToolGrid','projectImageUrl','projectLink',script)(Vue,()=>{calls.push('create');return collector},()=>({status:Vue.ref('ready'),error:Vue.ref(''),gridItems:Vue.ref([]),diceVisible:Vue.ref(false),load:()=>{}}),async()=>{if(failContent)throw new Error('offline');return []},project,null,null,null,null,()=>null,()=>null)
 const renderer=Vue.createRenderer({createComment:()=>({}),insert:()=>{},remove:()=>{},parentNode:()=>null,nextSibling:()=>null})
 const app=renderer.createApp({...component,render:()=>null});const instance=app.mount({})
 const state=instance.$.setupState
 state.detailsDialog={open:false,showModal(){this.open=true},scrollTop:0}
 return {calls,state,window,unmount(){app.unmount();Object.assign(globalThis,previous)}}
}

test('real public App records homepage despite content failure and only successful open details',async()=>{
 const page=mountPublic({failContent:true})
 try {
  await flush();assert.deepEqual(page.calls,['create','website'])
  await page.state.showProject({id:4});assert.deepEqual(page.calls,['create','website',['project',4]])
  for(const value of [null,0,-1,'4',NaN,2**53])page.window.dispatchEvent(new CustomEvent('project-opened',{detail:{project_id:value}}))
  assert.equal(page.calls.length,3)
 }finally{page.unmount()}
 assert.equal(page.calls.at(-1),'dispose')
 page.window.dispatchEvent(new CustomEvent('project-opened',{detail:{project_id:4}}));assert.equal(page.calls.at(-1),'dispose')
})
test('non-home public path and failed or closed detail do not collect project views',async()=>{
 for(const path of ['/trip/','/admin']){const page=mountPublic({path});try{await flush();assert.deepEqual(page.calls,[])}finally{page.unmount()}}
 const failed=mountPublic({project:async()=>{throw new Error('not found')}})
 try{await flush();await failed.state.showProject({id:4});assert.deepEqual(failed.calls,['create','website'])}finally{failed.unmount()}
 let resolve;const page=mountPublic({project:()=>new Promise(r=>resolve=r)})
 try{await flush();const opening=page.state.showProject({id:4});page.state.detailsDialog.open=false;page.state.restoreScroll();resolve({id:4});await opening;assert.deepEqual(page.calls,['create','website'])}finally{page.unmount()}
})


test('saved blank About fields use defaults while nonempty text and current project survive',async()=>{
 const page=mountPublic()
 try{
  await flush()
  page.state.projects=[{id:1,name:'数据库中的项目'}]
  page.state.profile={name:'rewind',title:'',introduction:'',skills:[],about_content:{page_title:'',about_body:'',current_project_url:'',contact_heading:'写信给我'}}
  await Vue.nextTick()
  assert.equal(page.state.about.page_title,'关于我')
  assert.equal(page.state.about.about_body,'在这里整理项目，也为学习记录和小实验留一个位置。')
  assert.equal(page.state.about.current_project_label,'数据库中的项目')
  assert.equal(page.state.about.current_project_url,'/#/works')
  assert.equal(page.state.about.contact_heading,'写信给我')
 }finally{page.unmount()}
})
