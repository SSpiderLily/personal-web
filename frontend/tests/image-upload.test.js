import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'

function mount(api, modelValue = null) {
  const path = new URL('../src/admin/ImageUpload.vue', import.meta.url)
  assert.ok(existsSync(path), 'ImageUpload has not been implemented')
  const { descriptor } = parse(readFileSync(path, 'utf8'))
  const source = compileScript(descriptor, { id: 'image-upload-test' }).content
    .replace(/import \{([^}]+)\} from ['"]vue['"]/g, (_, names) => 'const {' + names.replace(/(\w+) as (\w+)/g, '$1: $2') + '} = Vue')
    .replace('export default', 'return')
  const component = new Function('Vue', source)(Vue)
  const emitted = []
  const state = component.setup({ api, modelValue }, { expose() {}, emit: (...event) => emitted.push(event) })
  return { state, emitted }
}
const oldValue = { id: 'old', media_type: 'image/png', byte_size: 30, width: 2, height: 2, url: '/api/admin/files/old' }
const file = { name: 'new.png', type: 'image/png', size: 100 }

test('success uploads a selected file and emits metadata', async () => {
  let received
  const value = { ...oldValue, id: 'new', url: '/api/admin/files/new' }
  const page = mount({ upload: async input => { received = input; return value } }, oldValue)
  await page.state.selectFile({ target: { files: [file], value: 'x' } })
  assert.equal(received, file)
  assert.deepEqual(page.emitted, [['update:modelValue', value]])
  assert.equal(page.state.busy.value, false)
})

test('failure preserves the previous value and displays a generic message', async () => {
  const page = mount({ upload: async () => { throw new Error('/private/path secret') } }, oldValue)
  await page.state.selectFile({ target: { files: [file], value: 'x' } })
  assert.deepEqual(page.emitted, [])
  assert.ok(page.state.error.value)
  assert.doesNotMatch(page.state.error.value, /secret|private/)
})

test('401 emits unauthenticated without clearing the previous image', async () => {
  const page = mount({ upload: async () => { throw { status: 401, code: 'unauthenticated' } } }, oldValue)
  await page.state.selectFile({ target: { files: [file], value: 'x' } })
  assert.deepEqual(page.emitted, [['unauthenticated']])
})

test('busy state prevents duplicate upload and clears input so same file can retry', async () => {
  let calls = 0, resolve
  const page = mount({ upload: () => { calls++; return new Promise(done => { resolve = done }) } })
  const target = { files: [file], value: 'x' }
  const pending = page.state.selectFile({ target })
  assert.equal(page.state.busy.value, true)
  await page.state.selectFile({ target })
  assert.equal(calls, 1)
  resolve(oldValue)
  await pending
  assert.equal(target.value, '')
  assert.equal(page.state.busy.value, false)
})

test('client rejects empty, oversized and unsupported files before network', async () => {
  let calls = 0
  const page = mount({ upload: async () => { calls++; return oldValue } })
  for (const invalid of [{ ...file, size: 0 }, { ...file, size: 10485761 }, { ...file, type: 'image/svg+xml' }]) {
    await page.state.selectFile({ target: { files: [invalid], value: 'x' } })
    assert.ok(page.state.error.value)
  }
  assert.equal(calls, 0)
  assert.deepEqual(page.emitted, [])
})
