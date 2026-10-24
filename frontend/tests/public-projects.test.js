import test from 'node:test'
import assert from 'node:assert/strict'
import { fetchProjects, fetchProject } from '../src/projects/publicProjects.js'
const item={id:4,name:'项目',summary:'简介',category:'',tech_stack:['Vue'],features:[],cover_file_id:null,cover_alt:'',demo_url:null,source_url:null,blocks:[{kind:'text',body:'内容'}],screenshots:[],status:'published',sort_order:0,published_at:'2026-10-24T00:00:00Z',updated_at:'2026-10-24T00:00:00Z'}
const response=value=>({ok:true,json:async()=>value})
test('public projects read database contract with no cache',async()=>{
 let call;const fetcher=async(url,options)=>{call={url,options};return response({projects:[item]})}
 const projects=await fetchProjects(fetcher);assert.equal(projects[0].id,4);assert.equal(call.url,'/api/projects');assert.equal(call.options.cache,'no-store')
 assert.equal((await fetchProject(4,async()=>response({project:item}))).id,4)
})
test('public reads reject nonpublished, malformed, mismatched and failed responses',async()=>{
 await assert.rejects(fetchProjects(async()=>response({projects:[{...item,status:'draft'}]})))
 await assert.rejects(fetchProjects(async()=>response({projects:'invalid'})))
 await assert.rejects(fetchProject(5,async()=>response({project:item})))
 await assert.rejects(fetchProjects(async()=>({ok:false})))
 assert.deepEqual(await fetchProjects(async()=>response({projects:[]})),[])
})
