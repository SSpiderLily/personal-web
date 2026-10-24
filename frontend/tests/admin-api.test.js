import test from 'node:test'
import assert from 'node:assert/strict'
import { createAdminApi } from '../src/admin/adminApi.js'

const anonymous = { authenticated: false, admin: null, csrf_token: null, expires_at: null }
const session = { authenticated: true, admin: { id: 1, username: 'admin' }, csrf_token: 'a'.repeat(64), expires_at: '2030-01-01T00:00:00Z' }
const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body })

test('session uses same-origin credentials and never browser storage', async () => {
  let call
  const api = createAdminApi(async (url, options) => { call = { url, options }; return response(anonymous) })
  assert.deepEqual(await api.session(), anonymous)
  assert.equal(call.url, '/api/admin/session')
  assert.equal(call.options.credentials, 'same-origin')
  assert.equal(call.options.cache, 'no-store')
  assert.equal(call.options.method, 'GET')
})

test('login and logout send explicit JSON write protection and no credentials in URL', async () => {
  const calls = []
  const api = createAdminApi(async (url, options) => { calls.push({ url, options }); return response(url.endsWith('/logout') ? anonymous : session) })
  await api.login('admin', ' test password ', session.csrf_token)
  await api.logout(session.csrf_token)
  assert.equal(calls[0].url, '/api/admin/login')
  assert.deepEqual(JSON.parse(calls[0].options.body), { username: 'admin', password: ' test password ' })
  assert.equal(calls[0].options.headers['X-Admin-Request'], '1')
  assert.equal(calls[0].options.headers['X-CSRF-Token'], session.csrf_token)
  assert.equal(calls[0].options.headers['Content-Type'], 'application/json')
  assert.equal(calls[1].options.headers['X-CSRF-Token'], session.csrf_token)
  assert.equal(calls[1].options.credentials, 'same-origin')
})

test('credential failures expose only a mapped message, never server input or request body', async () => {
  const api = createAdminApi(async () => response({ error: { code: 'invalid_credentials', message: 'leaked secret password' } }, 401))
  await assert.rejects(api.login('admin', 'secret password'), error => {
    assert.equal(error.code, 'invalid_credentials')
    assert.match(error.message, /账号或密码/)
    assert.doesNotMatch(error.message, /secret|leaked/)
    return true
  })
})

test('malformed authenticated session cannot open the admin workspace', async () => {
  const api = createAdminApi(async () => response({ authenticated: true, admin: { id: 1, username: 'admin' } }))
  await assert.rejects(api.session(), error => error.code === 'unexpected_response')
})

test('network errors remain generic and do not echo error details', async () => {
  const api = createAdminApi(async () => { throw new Error('sensitive transport detail') })
  await assert.rejects(api.session(), error => {
    assert.equal(error.code, 'network_error')
    assert.doesNotMatch(error.message, /sensitive/)
    return true
  })
})

test('login and logout reject contradictory success payloads', async () => {
  const login = createAdminApi(async () => response(anonymous))
  await assert.rejects(login.login('admin', 'test password'), error => error.code === 'unexpected_response')
  const logout = createAdminApi(async () => response(session))
  await assert.rejects(logout.logout(session.csrf_token), error => error.code === 'unexpected_response')
})

const tools = {tools:[...Array.from({length:9},(_,i)=>({tool_key:`grid_0${i+1}`,placement:'grid',is_visible:true,sort_order:i})),{tool_key:'dice',placement:'floating',is_visible:true,sort_order:0}]}
test('tool settings use protected JSON PUT with bound CSRF and validate complete response',async()=>{
 const calls=[];const api=createAdminApi(async(url,options)=>{calls.push({url,options});return response(tools)})
 assert.deepEqual(await api.tools(),tools); await api.saveTools(tools,session.csrf_token)
 assert.equal(calls[1].url,'/api/admin/tools');assert.equal(calls[1].options.method,'PUT');assert.equal(calls[1].options.headers['X-CSRF-Token'],session.csrf_token)
 const bad=createAdminApi(async()=>response({tools:[]})); await assert.rejects(bad.tools(),e=>e.code==='unexpected_response')
})
test('file uploads use FormData without manual Content-Type and validate returned metadata',async()=>{
 let call;const metadata={id:'e829699d-abf4-4aa4-b02e-b067b36123e4',media_type:'image/png',byte_size:4,width:2,height:2,url:'/api/admin/files/e829699d-abf4-4aa4-b02e-b067b36123e4'}
 const api=createAdminApi(async(url,options)=>{call={url,options};return response(metadata,201)})
 assert.deepEqual(await api.uploadFile(new File(['test'],'test.png'),session.csrf_token),metadata)
 assert.equal(call.url,'/api/admin/files');assert.ok(call.options.body instanceof FormData);assert.equal(call.options.headers['Content-Type'],undefined);assert.equal(call.options.headers['X-CSRF-Token'],session.csrf_token)
 const bad=createAdminApi(async()=>response({...metadata,url:'https://other.example/secret'}));await assert.rejects(bad.uploadFile(new File(['test'],'test.png'),session.csrf_token),e=>e.code==='unexpected_response')
})

test('content methods use one protected request adapter and fixed routes', async () => {
 const calls=[]; const api=createAdminApi(async(url,options)=>{calls.push({url,options}); return response({project:{id:4},projects:[],name:''})})
 await api.projects(); await api.project(4); await api.createProject({name:'草稿'},'csrf'); await api.saveProject(4,{name:'编辑'},'csrf')
 await api.publishProject(4,'csrf'); await api.archiveProject(4,'csrf'); await api.reorderProjects([4],'csrf'); await api.profile(); await api.saveProfile({name:''},'csrf')
 assert.deepEqual(calls.map(x=>[x.url,x.options.method]),[
 ['/api/admin/projects','GET'],['/api/admin/projects/4','GET'],['/api/admin/projects','POST'],['/api/admin/projects/4','PUT'],
 ['/api/admin/projects/4/publish','POST'],['/api/admin/projects/4/archive','POST'],['/api/admin/projects/order','PUT'],['/api/admin/profile','GET'],['/api/admin/profile','PUT']])
 for (const call of calls.filter(x=>x.options.method!=='GET')) {assert.equal(call.options.headers['X-CSRF-Token'],'csrf');assert.equal(call.options.headers['X-Admin-Request'],'1')}
 assert.deepEqual(JSON.parse(calls[6].options.body),{ids:[4]})
})
