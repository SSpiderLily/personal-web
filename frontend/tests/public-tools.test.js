import test from 'node:test'
import assert from 'node:assert/strict'
import * as Vue from 'vue'
import { parseToolSettings, usePublicTools } from '../src/tools/publicTools.js'
const defaults = () => ({ tools: [ ...Array.from({length:9},(_,i)=>({tool_key:`grid_0${i+1}`,placement:'grid',is_visible:true,sort_order:i})), {tool_key:'dice',placement:'floating',is_visible:true,sort_order:0} ] })
const flush = async () => { await new Promise(resolve=>setImmediate(resolve)); await Vue.nextTick() }
function mount(fetcher) {
  let state
  const renderer=Vue.createRenderer({createComment:()=>({}),insert(){},remove(){},parentNode(){},nextSibling(){}})
  const app=renderer.createApp({setup(){state=usePublicTools(fetcher);return()=>null}})
  app.mount({})
  return {state,unmount:()=>app.unmount()}
}
test('tools contract rejects partial, duplicate and malformed settings instead of inventing defaults',()=>{
  const value=defaults(); const parsed=parseToolSettings(value)
  value.tools[0].is_visible=false
  assert.equal(parsed.tools[0].is_visible,true)
  for (const mutate of [v=>v.tools.pop(),v=>v.tools[0].tool_key='unknown',v=>v.tools[0].is_visible='false',v=>v.tools[1].sort_order=0,v=>v.tools[0].placement='floating',v=>v.tools[0].sort_order=true]) {
    const broken=defaults(); mutate(broken); assert.throws(()=>parseToolSettings(broken))
  }
})
test('public tools stay unmounted while loading and respect persisted visibility/order',async()=>{
  let resolve
  const page=mount(async()=>new Promise(r=>{resolve=r}))
  try {
    assert.equal(page.state.diceVisible.value,false); assert.deepEqual(page.state.gridItems.value,[])
    const value=defaults(); value.tools[0].is_visible=false; value.tools[1].sort_order=8; value.tools[8].sort_order=1; value.tools[9].is_visible=false
    resolve({ok:true,json:async()=>value}); await flush()
    assert.equal(page.state.status.value,'ready'); assert.equal(page.state.diceVisible.value,false)
    assert.equal(page.state.gridItems.value[0].tool_key,'grid_09'); assert.equal(page.state.gridItems.value.length,8)
  } finally {page.unmount()}
})
test('failure, malformed response and all-hidden success never resurrect default tools; retry works',async()=>{
  let attempt=0
  const page=mount(async()=>{attempt++; if(attempt===1)throw Error('private'); if(attempt===2)return{ok:true,json:async()=>({tools:[]})}; const value=defaults(); value.tools.forEach(t=>t.is_visible=false); return{ok:true,json:async()=>value}})
  try {
    await flush(); assert.equal(page.state.status.value,'error'); assert.equal(page.state.diceVisible.value,false); assert.doesNotMatch(page.state.error.value,/private/)
    await page.state.load(); assert.equal(page.state.status.value,'error'); assert.deepEqual(page.state.gridItems.value,[])
    await page.state.load(); assert.equal(page.state.status.value,'ready'); assert.equal(page.state.diceVisible.value,false); assert.deepEqual(page.state.gridItems.value,[])
  } finally {page.unmount()}
})
test('public tools use same-origin no-store and abort pending work on unmount',async()=>{
  let options,resolve
  const page=mount(async(_url,o)=>{options=o;return new Promise(r=>{resolve=r})})
  assert.equal(options.credentials,'same-origin'); assert.equal(options.cache,'no-store')
  page.unmount(); assert.equal(options.signal.aborted,true)
  resolve({ok:true,json:async()=>defaults()}); await flush(); assert.equal(page.state.diceVisible.value,false)
})
