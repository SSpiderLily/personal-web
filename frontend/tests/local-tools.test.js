import test from 'node:test'
import assert from 'node:assert/strict'
import { imageSize, validateImageFile, outputName } from '../src/tools/imageProcessing.js'
import { canvasPoint, createHistory } from '../src/tools/drawing.js'

test('image resizing preserves aspect ratio, limits long edge and never upscales', () => {
  assert.deepEqual(imageSize(4000, 3000, 1920), { width: 1920, height: 1440 })
  assert.deepEqual(imageSize(3000, 4000, 1920), { width: 1440, height: 1920 })
  assert.deepEqual(imageSize(640, 480, 1920), { width: 640, height: 480 })
  assert.throws(() => imageSize(0, 200, 1920))
  assert.throws(() => imageSize(10000, 10000, 1920))
  assert.throws(() => imageSize(400, 300, NaN))
  assert.throws(() => imageSize(400, 300, 1.5))
})

test('image validation rejects unsupported or oversized files and chooses correct extension', () => {
  assert.doesNotThrow(() => validateImageFile({ type: 'image/png', size: 1234 }))
  assert.throws(() => validateImageFile({ type: 'image/svg+xml', size: 1234 }))
  assert.throws(() => validateImageFile({ type: 'image/jpeg', size: 21 * 1024 * 1024 }))
  assert.throws(() => validateImageFile({ type: 'image/png', size: 0 }))
  assert.equal(outputName('holiday.photo.png', 'image/jpeg'), 'holiday.photo-compressed.jpg')
  assert.equal(outputName('holiday.jpeg', 'image/webp'), 'holiday-compressed.webp')
})

test('pointer coordinates account for displayed canvas scaling and clamp edges', () => {
  const rect = { left: 20, top: 40, width: 600, height: 400 }
  assert.deepEqual(canvasPoint(320, 240, rect, 1200, 800), { x: 600, y: 400 })
  assert.deepEqual(canvasPoint(10, 900, rect, 1200, 800), { x: 0, y: 800 })
})

test('drawing history supports undo clear, redo and discards redo after a new stroke', () => {
  const history = createHistory()
  history.push({ type: 'stroke', points: [{ x: 0, y: 0 }] })
  history.push({ type: 'clear' })
  assert.equal(history.items.length, 2)
  history.undo()
  assert.equal(history.items.length, 1)
  history.redo()
  assert.equal(history.items.at(-1).type, 'clear')
  history.undo()
  history.push({ type: 'stroke', points: [{ x: 1, y: 2 }] })
  history.redo()
  assert.equal(history.items.length, 2)
  assert.equal(history.canRedo, false)
  history.undo(); history.undo(); history.undo()
  assert.equal(history.items.length, 0)
  assert.equal(history.canUndo, false)
})

test('unsaved editor can postpone hash navigation without losing the current page', async () => {
  const { allowPageNavigation } = await import('../src/tools/navigationGuard.js')
  const browser = new EventTarget()
  browser.location = { hash: '#/home' }
  let restored
  browser.history = { replaceState(_state, _title, hash) { restored = hash } }
  let requested
  const postpone = event => { requested = event.detail.hash; event.preventDefault() }
  browser.addEventListener('site-before-navigate', postpone)
  assert.equal(allowPageNavigation(browser, 'works', 'home'), false)
  assert.equal(restored, '#/works')
  assert.equal(requested, '#/home')
  browser.removeEventListener('site-before-navigate', postpone)
  assert.equal(allowPageNavigation(browser, 'works', 'home'), true)
})
