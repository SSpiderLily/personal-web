import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'

function mountAdmin(demoEnabled) {
  const source = readFileSync(new URL('../src/admin/AdminApp.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'admin-shell-test', inlineTemplate: true }).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) =>
      'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace('export default', 'return')
  const component = new Function('Vue', compiled)(Vue)
  const element = (type, text = '') => ({ type, text, props: {}, children: [], parent: null })
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
  const app = renderer.createApp(component, { demoEnabled })
  app.mount(root)
  const nodes = () => { const all = []; const visit = node => { all.push(node); node.children.forEach(visit) }; visit(root); return all }
  const text = () => nodes().map(node => node.text).join(' ')
  const find = (type, label) => nodes().find(node => node.type === type && (!label || node.text === label))
  return { text, find, nodes, unmount: () => app.unmount() }
}

// Removing the production gate would expose the preview workspace.
test('production mode never enters a mock session even after a submitted form', async () => {
  const page = mountAdmin(false)
  try {
    assert.match(page.text(), /真实登录尚未接入/)
    assert.ok(['', true].includes(page.find('input').props.disabled))
    assert.equal(page.find('button', '进入本地演示'), undefined)
    page.find('form').props.onSubmit({ preventDefault() {} })
    await Vue.nextTick()
    assert.equal(page.find('nav'), undefined)
  } finally { page.unmount() }
})

// Accepting a password or issuing any request/storage write would break this contract.
test('development preview opens without credentials and has no network or persistent session', async () => {
  const page = mountAdmin(true)
  const originalFetch = globalThis.fetch
  globalThis.fetch = () => { throw new Error('mock login must not call the backend') }
  try {
    assert.match(page.text(), /请勿输入真实密码/)
    assert.ok(['', true].includes(page.nodes().find(node => node.props.type === 'password').props.disabled))
    assert.ok(page.find('button', '进入本地演示'))
    page.find('form').props.onSubmit({ preventDefault() {} })
    await Vue.nextTick()
    assert.ok(page.find('nav'))
    assert.match(page.text(), /本地演示会话/)
    assert.match(page.text(), /尚未接入/)
  } finally { globalThis.fetch = originalFetch; page.unmount() }
})

// A broken navigation handler, exit handler, or persisted session would fail this flow.
test('preview navigation shows pending modules and exit/remount returns to the login screen', async () => {
  const page = mountAdmin(true)
  try {
    page.find('form').props.onSubmit({ preventDefault() {} })
    await Vue.nextTick()
    for (const label of ['项目管理', '访问统计', '网站内容', '小工具管理']) {
      page.find('button', label).props.onClick()
      await Vue.nextTick()
      assert.equal(page.find('h1').text, label)
      assert.match(page.text(), /尚未接入/)
      assert.equal(page.nodes().filter(node => node.type === 'input').length, 0)
    }
    page.find('button', '退出演示').props.onClick()
    await Vue.nextTick()
    assert.ok(page.find('form'))
    assert.equal(page.find('nav'), undefined)
  } finally { page.unmount() }
  const fresh = mountAdmin(true)
  try { assert.ok(fresh.find('form')); assert.equal(fresh.find('nav'), undefined) }
  finally { fresh.unmount() }
})
