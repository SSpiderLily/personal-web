import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'

globalThis.matchMedia = () => ({ matches: false })

// Compile the real component script; substitute only its module boundaries.
function mountDice(loadScene, getValue) {
  const source=readFileSync(new URL('../src/components/DiceGame.vue',import.meta.url),'utf8')
  const {descriptor}=parse(source)
  const compiled=compileScript(descriptor,{id:'dice-lifecycle-test'}).content
    .replace(/^import .*$/gm,'')
    .replace("import('../dice/createDiceScene.js')",'loadScene()')
    .replace('export default','return')
  const component=new Function('Vue','requestDiceValue','loadScene',
    'const {onMounted,onBeforeUnmount,ref}=Vue;'+compiled)(Vue,getValue,loadScene)
  const renderer=Vue.createRenderer({
    createComment:()=>({}),insert(){},remove(){},parentNode(){return null},nextSibling(){return null},
  })
  const app=renderer.createApp({...component,render:()=>null})
  const instance=app.mount({})
  return {state:instance.$.setupState,unmount:()=>app.unmount()}
}
const flush=()=>new Promise(resolve=>setImmediate(resolve))

test('late 3D initialization preserves a result already obtained from the backend',async()=>{
  let load,shown=1
  const mounted=mountDice(()=>new Promise(resolve=>{load=resolve}),async()=>6)
  try {
    await mounted.state.roll()
    assert.equal(mounted.state.value,6)
    load({createDiceScene:()=>({rollTo:async value=>{shown=value},dispose(){}})})
    await flush()
    assert.equal(mounted.state.ready,true)
    assert.equal(shown,6)
  } finally {mounted.unmount()}
})
test('context loss exposes the fallback and restores the most recent backend result',async()=>{
  let notify,shown=1,value=4
  const mounted=mountDice(async()=>({createDiceScene:(_canvas,options)=>{
    notify=options?.onAvailabilityChange
    return {rollTo:async result=>{shown=result},dispose(){}}
  }}),async()=>value)
  try {
    await flush()
    await mounted.state.roll()
    assert.equal(shown,4)
    assert.equal(typeof notify,'function')
    notify(false)
    assert.equal(mounted.state.ready,false)
    value=6
    await mounted.state.roll()
    assert.equal(mounted.state.value,6)
    notify(true)
    assert.equal(shown,6)
    assert.equal(mounted.state.ready,true)
  } finally {mounted.unmount()}
})
test('unmount aborts a pending backend request and disposes the scene',async()=>{
  let signal,disposed=false
  const mounted=mountDice(async()=>({createDiceScene:()=>({rollTo:async()=>{},dispose(){disposed=true}})}),
    options=>new Promise((_resolve,reject)=>{signal=options.signal;signal.addEventListener('abort',()=>reject(signal.reason),{once:true})}))
  await flush()
  const roll=mounted.state.roll()
  mounted.unmount()
  await roll
  assert.equal(signal.aborted,true)
  assert.equal(disposed,true)
})
test('repeated clicks during a pending request send one request',async()=>{
  let calls=0,resolveRequest
  const mounted=mountDice(async()=>{throw Error('WebGL unavailable')},()=>{
    calls++;return new Promise(resolve=>{resolveRequest=resolve})
  })
  try {
    await flush()
    const first=mounted.state.roll()
    await mounted.state.roll()
    assert.equal(calls,1)
    resolveRequest(3)
    await first
    assert.equal(mounted.state.value,3)
    assert.equal(mounted.state.ready,false)
  } finally {mounted.unmount()}
})

test('reduced-motion preference displays the backend result without a flight',async()=>{
  let options
  globalThis.matchMedia=()=>({matches:true})
  const mounted=mountDice(async()=>({createDiceScene:()=>({rollTo:async(_value,config)=>{options=config},dispose(){}})}),async()=>5)
  try {
    await flush()
    await mounted.state.roll()
    assert.equal(options.reducedMotion,true)
    assert.equal(mounted.state.value,5)
  } finally {mounted.unmount();globalThis.matchMedia=()=>({matches:false})}
})
