<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { canvasPoint, createHistory, paintStroke } from '../tools/drawing.js'
import { encodeCanvas } from '../tools/imageProcessing.js'

const emit = defineEmits(['dirty'])
const canvas = ref(null), tool = ref('brush'), color = ref('#36553d'), width = ref(8)
const canUndo = ref(false), canRedo = ref(false), clearPending = ref(false), saving = ref(false), error = ref(''), saved = ref(false)
const palette = ['#36553d', '#222222', '#ffffff', '#ca5346', '#db9d3a', '#4673ac', '#9562a9', '#de8f9a']
const history = createHistory()
let context, active = null, pointer = null, revision = 0, alive = true
const downloadUrls = new Set(), downloadTimers = new Set()
function markChanged() {
  revision++; saved.value = false
  canUndo.value = history.canUndo; canRedo.value = history.canRedo
  emit('dirty', true)
}
function redraw() {
  if (!context) return
  context.clearRect(0, 0, canvas.value.width, canvas.value.height)
  for (const action of history.items) {
    if (action.type === 'clear') context.clearRect(0, 0, canvas.value.width, canvas.value.height)
    else paintStroke(context, action)
  }
}
function point(event) { return canvasPoint(event.clientX, event.clientY, canvas.value.getBoundingClientRect(), canvas.value.width, canvas.value.height) }
function start(event) {
  if (!context || pointer !== null || (event.pointerType === 'mouse' && event.button !== 0)) return
  event.preventDefault()
  canvas.value.focus({ preventScroll: true })
  pointer = event.pointerId
  canvas.value.setPointerCapture(pointer)
  active = { type: 'stroke', eraser: tool.value === 'eraser', color: color.value, width: Number(width.value), points: [point(event)] }
  clearPending.value = false
  paintStroke(context, active)
  emit('dirty', true)
}
function move(event) {
  if (!active || event.pointerId !== pointer) return
  const next = point(event), last = active.points.at(-1)
  if (Math.hypot(next.x - last.x, next.y - last.y) < 1) return
  active.points.push(next)
  paintStroke(context, { ...active, points: [last, next] })
}
function end(event) {
  if (!active || event.pointerId !== pointer) return
  history.push(active)
  active = null; pointer = null
  markChanged()
}
function undo() { if (active) return; history.undo(); clearPending.value = false; redraw(); markChanged() }
function redo() { if (active) return; history.redo(); clearPending.value = false; redraw(); markChanged() }
function clear() {
  if (active) return
  history.push({ type: 'clear' })
  clearPending.value = false; redraw(); markChanged()
}
async function download() {
  if (!context || saving.value || active) return
  saving.value = true; error.value = ''
  const version = revision
  try {
    const output = document.createElement('canvas')
    output.width = canvas.value.width; output.height = canvas.value.height
    const ctx = output.getContext('2d')
    if (!ctx) throw new Error('当前浏览器无法导出图片。')
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, output.width, output.height)
    ctx.drawImage(canvas.value, 0, 0)
    const blob = await encodeCanvas(output, 'image/png')
    if (!alive) return
    const url = URL.createObjectURL(blob), anchor = document.createElement('a')
    downloadUrls.add(url)
    anchor.href = url; anchor.download = 'my-drawing.png'
    document.body.append(anchor); anchor.click(); anchor.remove()
    const timer = setTimeout(() => { URL.revokeObjectURL(url); downloadUrls.delete(url); downloadTimers.delete(timer) }, 30000)
    downloadTimers.add(timer)
    if (version === revision && !active) { saved.value = true; emit('dirty', false) }
  } catch (reason) { if (alive) error.value = reason.message || '图片导出失败，请重试。' }
  finally { if (alive) saving.value = false }
}
function shortcuts(event) {
  if (!['CANVAS', 'SECTION'].includes(event.target.tagName)) return
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault()
    if (event.shiftKey && canRedo.value) redo()
    else if (!event.shiftKey && canUndo.value) undo()
  }
}
onMounted(() => {
  context = canvas.value.getContext('2d')
  if (!context) error.value = '当前浏览器不支持画板，请使用支持 Canvas 的浏览器。'
})
onBeforeUnmount(() => { alive = false; downloadTimers.forEach(clearTimeout); downloadUrls.forEach(url => URL.revokeObjectURL(url)) })
</script>

<template>
  <section class="local-tool drawing-board" aria-label="本站画板" @keydown="shortcuts">
    <div class="drawing-toolbar">
      <div class="drawing-modes" role="group" aria-label="绘画工具"><button type="button" :aria-pressed="tool === 'brush'" @click="tool = 'brush'">画笔</button><button type="button" :aria-pressed="tool === 'eraser'" @click="tool = 'eraser'">橡皮</button></div>
      <label class="color-picker">颜色<input v-model="color" type="color" aria-label="画笔颜色" @input="tool = 'brush'"></label>
      <label class="brush-width">粗细 · {{ width }} px<input v-model="width" type="range" min="1" max="60" aria-label="画笔粗细"></label>
      <div class="drawing-actions"><button type="button" :disabled="!canUndo" @click="undo">撤销</button><button type="button" :disabled="!canRedo" @click="redo">重做</button><button type="button" @click="clearPending = !clearPending">清空</button><button type="button" class="local-primary" :disabled="saving" @click="download">{{ saving ? '正在导出…' : '下载 PNG ↓' }}</button></div>
    </div>
    <div class="drawing-palette" role="group" aria-label="常用颜色"><button v-for="value in palette" :key="value" type="button" :style="{ background: value }" :aria-label="`选择颜色 ${value}`" :aria-pressed="color === value" @click="color = value; tool = 'brush'"></button><span>1200 × 800 · 白色背景导出</span></div>
    <div v-if="clearPending" class="local-confirm" role="alert"><span>清空画布？清空后仍可撤销。</span><button type="button" @click="clear">确认清空</button><button type="button" @click="clearPending = false">取消</button></div>
    <p v-if="error" class="local-error" role="alert">{{ error }}</p>
    <div class="drawing-surface"><canvas ref="canvas" width="1200" height="800" tabindex="0" aria-label="绘画画布，支持鼠标或触摸绘画" @pointerdown="start" @pointermove="move" @pointerup="end" @pointercancel="end" @lostpointercapture="end" @contextmenu.prevent>浏览器需要支持 Canvas 才能绘画。</canvas></div>
    <p class="local-hint" role="status">{{ saved ? '已发起 PNG 下载，请检查浏览器下载记录。' : '用鼠标、触控笔或手指绘画。Ctrl / ⌘ + Z 撤销，Shift + Ctrl / ⌘ + Z 重做。关闭前记得下载。' }}</p>
  </section>
</template>
