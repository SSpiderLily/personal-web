import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { AdminApiError } from '../src/admin/adminApi.js'
import { parseStatistics } from '../src/statistics/statisticsModel.js'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

function mountAdmin(api, { render = false } = {}) {
  const source = readFileSync(new URL('../src/admin/AdminApp.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'admin-shell-test', inlineTemplate: false })
  const compiled = script.content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) =>
      'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace(/^import.*from.*adminApi.*$/gm, '')
    .replace(/^import (ToolsPanel|ProjectsPanel|ProfilePanel|StatisticsPanel).*$/gm, '')
    .replace('export default', 'return')
  const childDescriptor = parse(readFileSync(new URL('../src/admin/ToolsPanel.vue', import.meta.url), 'utf8')).descriptor
  const childCode = compileScript(childDescriptor, { id: 'admin-tools-test', inlineTemplate: true }).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) =>
      'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace('export default', 'return')
  const ToolsPanel = new Function('Vue', childCode)(Vue)
  const ProjectsPanel = Vue.defineComponent({setup(){ const value=Vue.ref('');return()=>Vue.h('input',{value:value.value,onInput:e=>value.value=e.target.value},'module-draft') }})
  const ProfilePanel = Vue.defineComponent({setup(){return()=>Vue.h('p','profile module')}})
  const statsDescriptor = parse(readFileSync(new URL('../src/admin/StatisticsPanel.vue', import.meta.url), 'utf8')).descriptor
  const statsCode = compileScript(statsDescriptor, {id:'admin-statistics-test',inlineTemplate:true}).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) => 'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace(/^import.*statisticsModel.*$/gm, '').replace('export default','return')
  const StatisticsPanel = new Function('Vue','parseStatistics',statsCode)(Vue,parseStatistics)
  const component = new Function('Vue', 'createAdminApi', 'AdminApiError', 'ToolsPanel', 'ProjectsPanel', 'ProfilePanel', 'StatisticsPanel', compiled)(Vue, () => api, AdminApiError, ToolsPanel, ProjectsPanel, ProfilePanel, StatisticsPanel)
  const template = compileTemplate({ source: descriptor.template.content, id: 'admin-shell-test', compilerOptions: { bindingMetadata: script.bindings } }).code
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) =>
      'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace('export function render', 'return function render')
  component.render = new Function('Vue', template)(Vue)
  const element = (type, text = '') => ({ type, text, style: {}, props: {}, children: [], parent: null, events: {}, addEventListener(name, handler) { this.events[name] = handler } })
  const renderer = Vue.createRenderer({
    createElement: element, createText: text => element('#text', text),
    createComment: text => element('#comment', text),
    setText(node, text) { node.text = text },
    setElementText(node, text) { node.text = text; node.children = [] },
    patchProp(node, key, _old, value) { node.props[key] = value },
    insert(node, parent, anchor) {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
      const index = anchor ? parent.children.indexOf(anchor) : -1
      parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
      node.parent = parent
    },
    remove(node) { node.parent.children.splice(node.parent.children.indexOf(node), 1) },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1],
  })
  const root = element('root')
  const app = renderer.createApp(render ? component : { ...component, render: () => null }, { api })
  const instance = app.mount(root)
  const nodes = () => { const all = []; const visit = node => { all.push(node); node.children.forEach(visit) }; visit(root); return all }
  const text = () => nodes().map(node => node.text).join(' ')
  const find = (type, label) => nodes().find(node => node.type === type && (!label || node.text === label))
  return { state: instance.$.setupState, nodes, text, find, unmount: () => app.unmount() }
}


const anonymous = { authenticated: false, admin: null, csrf_token: null, expires_at: null }
const authenticated = { authenticated: true, admin: { id: 1, username: 'admin' }, csrf_token: 'a'.repeat(64), expires_at: '2030-01-01T00:00:00Z' }
const overview = { admin: authenticated.admin, modules: ['projects', 'statistics', 'content', 'tools'].map(id => ({ id, status: 'pending' })) }
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
function api(overrides = {}) {
  return { session: async () => anonymous, login: async () => authenticated, logout: async () => anonymous, overview: async () => overview, ...overrides }
}

test('session check fails closed and can retry without any simulated login', async () => {
  let failed = true
  const page = mountAdmin(api({ session: async () => {
    if (failed) throw new AdminApiError('network_error', 0)
    return anonymous
  } }))
  try {
    await flush()
    assert.equal(page.state.phase, 'unavailable')
    assert.equal(page.state.session, null)
    failed = false
    await page.state.restoreSession()
    assert.equal(page.state.phase, 'anonymous')
  } finally { page.unmount() }
})

test('anonymous focus refresh preserves a draft and still discovers sign-in from another tab', async () => {
  let current = anonymous, delayRefresh = false, resolveRefresh
  const page = mountAdmin(api({ session: async () => {
    if (delayRefresh) return new Promise(resolve => { resolveRefresh = resolve })
    return current
  } }))
  try {
    await flush()
    assert.equal(page.state.phase, 'anonymous')
    page.state.username = 'draft-admin'
    page.state.password = 'draft-password'
    delayRefresh = true
    const pending = page.state.restoreSession()
    assert.equal(page.state.phase, 'anonymous')
    resolveRefresh(anonymous)
    await pending
    assert.equal(page.state.username, 'draft-admin')
    assert.equal(page.state.password, 'draft-password')
    assert.equal(page.state.phase, 'anonymous')
    delayRefresh = false
    current = authenticated
    await page.state.restoreSession()
    assert.equal(page.state.phase, 'authenticated')
    assert.equal(page.state.session.admin.username, 'admin')
    assert.equal(page.state.password, '')
  } finally { page.unmount() }
})

test('login uses entered credentials once, clears password and opens the protected workspace', async () => {
  let resolveLogin, calls = 0, supplied
  const page = mountAdmin(api({ login: (username, password) => {
    calls++; supplied = { username, password }
    return new Promise(resolve => { resolveLogin = resolve })
  } }))
  try {
    await flush()
    page.state.username = ' admin '
    page.state.password = ' my real test password '
    const pending = page.state.login()
    await page.state.login()
    assert.equal(calls, 1)
    assert.deepEqual(supplied, { username: 'admin', password: ' my real test password ' })
    resolveLogin(authenticated)
    await pending
    assert.equal(page.state.phase, 'authenticated')
    assert.equal(page.state.password, '')
    assert.equal(page.state.session.admin.username, 'admin')
    assert.equal(page.state.overviewReady, true)
  } finally { page.unmount() }
})

test('invalid credentials keep login visible and never display or retain the entered password', async () => {
  const page = mountAdmin(api({ login: async () => { throw new AdminApiError('invalid_credentials', 401) } }))
  try {
    await flush()
    page.state.username = 'admin'
    page.state.password = 'do not echo this password'
    await page.state.login()
    assert.equal(page.state.phase, 'anonymous')
    assert.equal(page.state.session, null)
    assert.equal(page.state.password, '')
    assert.match(page.state.error, /账号或密码/)
    assert.doesNotMatch(page.state.error, /echo/)
  } finally { page.unmount() }
})

test('a new mount restores the database session and protected requests detect expiry', async () => {
  let expired = false
  const page = mountAdmin(api({
    session: async () => authenticated,
    overview: async () => {
      if (expired) throw new AdminApiError('unauthenticated', 401)
      return overview
    },
  }))
  try {
    await flush()
    assert.equal(page.state.phase, 'authenticated')
    expired = true
    await page.state.selectModule('statistics')
    assert.equal(page.state.phase, 'anonymous')
    assert.equal(page.state.session, null)
    assert.match(page.state.error, /失效/)
  } finally { page.unmount() }
})

test('logout failure does not pretend the server session was revoked; success clears it', async () => {
  let failed = true, token
  const page = mountAdmin(api({
    session: async () => authenticated,
    logout: async csrf => {
      token = csrf
      if (failed) throw new AdminApiError('network_error', 0)
      return anonymous
    },
  }))
  try {
    await flush()
    await page.state.logout()
    assert.equal(page.state.phase, 'authenticated')
    assert.equal(page.state.session.admin.id, 1)
    assert.ok(page.state.error)
    assert.equal(token, authenticated.csrf_token)
    failed = false
    page.state.password = 'should clear on logout'
    await page.state.logout()
    assert.equal(page.state.phase, 'anonymous')
    assert.equal(page.state.session, null)
    assert.equal(page.state.password, '')
  } finally { page.unmount() }
})

test('protected content failure stays retryable without making up module data', async () => {
  let failed = true
  const page = mountAdmin(api({
    session: async () => authenticated,
    overview: async () => {
      if (failed) throw new AdminApiError('admin_unavailable', 503)
      return overview
    },
  }), { render: true })
  try {
    await flush()
    assert.equal(page.state.phase, 'authenticated')
    assert.equal(page.state.overviewReady, false)
    assert.ok(page.state.error)
    failed = false
    await page.find('button', '重试').props.onClick()
    assert.equal(page.state.overviewReady, true)
    assert.equal(page.state.error, '')
  } finally { page.unmount() }
})

test('authenticated focus verification keeps mounted module content while the session remains valid',async()=>{
 let delay=false,resolve,overviewCalls=0
 const page=mountAdmin(api({session:async()=>delay?new Promise(r=>{resolve=r}):authenticated,overview:async()=>{overviewCalls++;return overview}}))
 try {
  await flush(); delay=true; const checking=page.state.restoreSession()
  assert.equal(page.state.phase,'authenticated'); assert.equal(page.state.overviewReady,true)
  resolve(authenticated); await checking
  assert.equal(page.state.phase,'authenticated'); assert.equal(page.state.overviewReady,true); assert.equal(overviewCalls,1)
 } finally {page.unmount()}
})

test('tools module adapter uses the live CSRF token and routes authentication loss to the login page',async()=>{
 let saved
 const payload={tools:[]}
 const page=mountAdmin(api({session:async()=>authenticated,tools:async()=>payload,saveTools:async(value,csrf)=>{saved={value,csrf};return value}}))
 try {
  await flush(); assert.deepEqual(await page.state.toolModuleApi.load(),payload)
  await page.state.toolModuleApi.save(payload); assert.equal(saved.csrf,authenticated.csrf_token)
  page.state.moduleUnauthenticated(); assert.equal(page.state.phase,'anonymous'); assert.equal(page.state.session,null)
 } finally {page.unmount()}
})

const toolSettings = () => ({ tools: [...Array.from({ length: 9 }, (_, i) => ({ tool_key: `grid_0${i + 1}`, placement: 'grid', is_visible: true, sort_order: i })), { tool_key: 'dice', placement: 'floating', is_visible: true, sort_order: 0 }] })
const diceCheckbox = page => page.nodes().find(node => node.props['aria-label'] === 'dice 显示')

for (const reason of [new AdminApiError('network_error'), new AdminApiError('admin_unavailable', 503)]) {
  test(`authenticated focus ${reason.code} and error-panel retry retain the real tools draft`, async () => {
    const previousWindow = globalThis.window
    const focusWindow = new EventTarget()
    globalThis.window = focusWindow
    let sessionResult = async () => authenticated, resolveRetry, suppliedCsrf
    const page = mountAdmin(api({
      session: () => sessionResult(),
      tools: async () => toolSettings(),
      saveTools: async (value, csrf) => { suppliedCsrf = csrf; return value },
    }), { render: true })
    try {
      await flush()
      await page.find('button', '小工具管理').props.onClick()
      await flush()
      const originalSession = page.state.session
      const originalInput = diceCheckbox(page)
      originalInput.checked = false
      originalInput.events.change({ target: originalInput })
      await Vue.nextTick()
      assert.match(page.text(), /有未保存的更改/)
      sessionResult = async () => { throw reason }
      focusWindow.dispatchEvent(new Event('focus'))
      await flush()
      assert.ok(diceCheckbox(page) === originalInput, 'focus failure must retain the mounted editor')
      assert.equal(originalInput.checked, false)
      assert.equal(page.state.phase, 'authenticated')
      assert.equal(page.state.session, originalSession)
      assert.equal(page.state.overviewReady, true)
      assert.match(page.text(), /有未保存的更改/)
      assert.ok(page.state.error)

      await page.find('button', '重试').props.onClick()
      await flush()
      assert.ok(diceCheckbox(page) === originalInput, 'failed retry must retain the mounted editor')
      assert.equal(originalInput.checked, false)
      assert.ok(page.state.error)

      sessionResult = () => new Promise(resolve => { resolveRetry = resolve })
      const retry = page.find('button', '重试').props.onClick()
      await Vue.nextTick()
      assert.ok(diceCheckbox(page) === originalInput, 'pending retry must retain the mounted editor')
      assert.equal(typeof resolveRetry, 'function', 'retry must verify the session')
      resolveRetry({ ...authenticated, csrf_token: 'b'.repeat(64) })
      await retry
      await flush()
      assert.ok(diceCheckbox(page) === originalInput, 'successful retry must retain the mounted editor')
      assert.equal(originalInput.checked, false)
      assert.match(page.text(), /有未保存的更改/)
      assert.equal(page.state.error, '')
      await page.find('button', '保存设置').props.onClick()
      await flush()
      assert.equal(suppliedCsrf, 'b'.repeat(64))
      assert.match(page.text(), /已保存/)
    } finally {
      page.unmount()
      if (previousWindow === undefined) delete globalThis.window
      else globalThis.window = previousWindow
    }
  })
}

for (const loss of ['anonymous', '401', 'unauthenticated']) {
  test(`authenticated focus ${loss} still removes the real editor and clears the session`, async () => {
    const previousWindow = globalThis.window
    const focusWindow = new EventTarget()
    globalThis.window = focusWindow
    let expired = false
    const page = mountAdmin(api({
      session: async () => {
        if (!expired) return authenticated
        if (loss === 'anonymous') return anonymous
        throw loss === '401' ? new AdminApiError('unexpected_response', 401) : new AdminApiError('unauthenticated')
      },
      tools: async () => toolSettings(),
    }), { render: true })
    try {
      await flush()
      await page.find('button', '小工具管理').props.onClick()
      await flush()
      assert.ok(diceCheckbox(page))
      expired = true
      focusWindow.dispatchEvent(new Event('focus'))
      await flush()
      assert.equal(diceCheckbox(page), undefined)
      assert.equal(page.state.phase, 'anonymous')
      assert.equal(page.state.session, null)
      assert.equal(page.state.overviewReady, false)
    } finally {
      page.unmount()
      if (previousWindow === undefined) delete globalThis.window
      else globalThis.window = previousWindow
    }
  })
}

for (const reason of [new AdminApiError('network_error'), new AdminApiError('admin_unavailable', 503)]) {
  test(`anonymous session refresh ${reason.code} still fails closed`, async () => {
    let failed = false
    const page = mountAdmin(api({ session: async () => {
      if (failed) throw reason
      return anonymous
    } }))
    try {
      await flush()
      assert.equal(page.state.phase, 'anonymous')
      page.state.password = 'unsent password'
      failed = true
      await page.state.restoreSession()
      assert.equal(page.state.phase, 'unavailable')
      assert.equal(page.state.session, null)
      assert.equal(page.state.overviewReady, false)
      assert.equal(page.state.password, '')
      assert.ok(page.state.error)
    } finally { page.unmount() }
  })
}

test('module switching and failed overview refresh preserve mounted content draft', async () => {
  let fail = false
  const page = mountAdmin(api({session:async()=>authenticated,overview:async()=>{if(fail)throw new AdminApiError('network_error');return overview}}),{render:true})
  try {
    await flush()
    const draft=page.find('input','module-draft')
    assert.ok(draft,'projects child should be mounted')
    draft.props.onInput({target:{value:'未保存的内容'}})
    await page.state.selectModule('content');await flush()
    await page.state.selectModule('projects');await flush()
    assert.equal(page.find('input','module-draft').props.value,'未保存的内容')
    fail=true;await page.state.refreshOverview();await flush()
    assert.equal(page.find('input','module-draft').props.value,'未保存的内容')
  } finally {page.unmount()}
})

test('statistics adapter forwards fixed ranges and delegates lost authentication',async()=>{
 const ranges=[];const page=mountAdmin(api({session:async()=>authenticated,statistics:async days=>{ranges.push(days);return {days}}}))
 try{await flush();assert.deepEqual(await page.state.statisticsModuleApi.load(30),{days:30});assert.deepEqual(ranges,[30]);page.state.moduleUnauthenticated();assert.equal(page.state.phase,'anonymous')}finally{page.unmount()}
})


test('real statistics child retries failures, shows true zero, preserves sibling draft, and clears on401',async()=>{
 let failure=503
 const page=mountAdmin(api({session:async()=>authenticated,statistics:async days=>{
  if(failure)throw new AdminApiError(failure===401?'unauthenticated':'admin_unavailable',failure)
  return {days,timezone:'Asia/Shanghai',start_date:'2026-10-18',end_date:'2026-10-24',website_visitors:0,projects:[]}
 }}),{render:true})
 try{
  await flush();page.find('input','module-draft').props.onInput({target:{value:'未保存'}})
  await page.state.selectModule('statistics');await flush();assert.match(page.text(),/访问统计暂时不可用/)
  assert.equal(page.find('input','module-draft').props.value,'未保存')
  failure=0;await page.find('button','重试加载').props.onClick();await flush()
  assert.ok(page.nodes().some(node=>node.props.class==='statistics-count'&&node.text==='0'))
  failure=401;await page.find('button','刷新').props.onClick();await flush()
  assert.equal(page.state.phase,'anonymous');assert.equal(page.find('input','module-draft'),undefined)
 }finally{page.unmount()}
})
