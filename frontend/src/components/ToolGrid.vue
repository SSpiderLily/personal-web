<script setup>
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import ImageCompressor from './ImageCompressor.vue'
import DrawingBoard from './DrawingBoard.vue'
import '../tools/local-tools.css'

// Keys preserve the existing administrator visibility and ordering settings.
const tools = {
  grid_01: { key: 'grid_01', name: '图片压缩', brand: 'IMAGE STUDIO', description: '压缩图片、转换格式，直观看到前后差别。', icon: 'M4 4h16v16H4zM4 16l5-5 4 4 3-3 4 4M8 8h.01' },
  grid_02: { key: 'grid_02', name: '随手画板', brand: 'LITTLE CANVAS', description: '选一支画笔，随手画下脑海里的小想法。', icon: 'm14 4 6 6M5 15 16 4a2 2 0 0 1 4 4L9 19l-6 2zM5 15l4 4' },
}
const dialog = ref(null)
const selected = ref(null)
const dirty = ref(false)
const closePending = ref(false)
let alive = true
let pendingHash = null
async function openTool(key) {
  selected.value = tools[key]
  dirty.value = false
  closePending.value = false
  await nextTick()
  if (alive) dialog.value?.showModal()
}
function requestClose() {
  if (dirty.value) closePending.value = true
  else dialog.value?.close()
}
function keepDrawing() { closePending.value = false; pendingHash = null }
function discardDrawing() {
  const hash = pendingHash
  dirty.value = false
  dialog.value?.close()
  if (hash !== null) window.location.hash = hash
}
function finishTool() { selected.value = null; dirty.value = false; closePending.value = false; pendingHash = null }
function beforeNavigate(event) {
  if (!selected.value || !dirty.value) return
  event.preventDefault()
  pendingHash = event.detail.hash
  closePending.value = true
}
function beforeUnload(event) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => {
  window.addEventListener('site-before-navigate', beforeNavigate)
  window.addEventListener('beforeunload', beforeUnload)
})
onBeforeUnmount(() => {
  alive = false
  window.removeEventListener('site-before-navigate', beforeNavigate)
  window.removeEventListener('beforeunload', beforeUnload)
  dialog.value?.close()
})
defineProps({ items: { type: Array, default: () => [] } })
const icons = Object.fromEntries([
  'M7 3h10v18H7zM10 7h4M10 11h1m2 0h1m-4 4h1m2 0h1m-4 3h4',
  'M12 8v5l3 2M9 2h6M12 2v3M18 5l2 2',
  'M8 8 3 12l5 4m8-8 5 4-5 4M14 4l-4 16',
  'M5 5h14v14H5zM9 9h6v6H9zM9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3',
  'M8 3H4v18h16V7l-4-4H8zM8 11h8M8 15h8M8 18h5M15 3v5h5',
  'm12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.4l6.1-.9z',
  'M8 7V4h12v12h-3M4 8h12v12H4z',
  'm15 15 6 6M7 10h6M10 7v6',
  'M5 12h14M12 5v14',
].map((path, index) => [`grid_${String(index + 1).padStart(2, '0')}`, { path, number: index + 1 }]))
</script>

<template>
  <ul class="tools-grid" aria-label="小工具">
    <li v-for="item in items" :key="item.tool_key" class="tool-cell" :class="{ 'tool-live': tools[item.tool_key] }" :aria-label="tools[item.tool_key]?.name || `工具占位 ${icons[item.tool_key]?.number}，尚未开放`">
      <button v-if="tools[item.tool_key]" class="tool-launch" type="button" :aria-label="`打开${tools[item.tool_key].name}`" aria-haspopup="dialog" @click="openTool(item.tool_key)">
        <span class="tool-brand">{{ tools[item.tool_key].brand }} <span aria-hidden="true">↗</span></span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="tools[item.tool_key].icon" /></svg>
        <strong>{{ tools[item.tool_key].name }}</strong>
        <span class="tool-description">{{ tools[item.tool_key].description }}</span>
        <span class="tool-action">打开工具 <span aria-hidden="true">→</span></span>
      </button>
      <template v-else>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle v-if="item.tool_key === 'grid_08'" cx="10" cy="10" r="6" />
          <circle v-if="item.tool_key === 'grid_09'" cx="12" cy="12" r="10" />
          <path :d="icons[item.tool_key]?.path" />
        </svg>
        <span class="placeholder-label">待开放</span>
      </template>
    </li>
  </ul>
  <p class="tool-note">本站小工具 · 图片处理与绘画都在你的浏览器中完成</p>
  <dialog ref="dialog" class="tool-dialog" aria-labelledby="tool-dialog-title" @close="finishTool" @cancel.prevent="requestClose">
    <template v-if="selected">
      <header class="tool-toolbar">
        <div><span class="tool-brand">{{ selected.brand }}</span><h2 id="tool-dialog-title">{{ selected.name }}</h2></div>
        <div class="tool-controls"><button type="button" class="tool-close" autofocus aria-label="关闭工具" @click="requestClose">关闭 ×</button></div>
      </header>
      <p class="tool-instructions">本地处理，不上传图片。关闭后不会保留编辑状态，请先下载结果。</p>
      <div v-if="closePending" class="tool-exit-confirm" role="alert"><span>画板还有未下载的内容，仍要关闭吗？</span><button type="button" @click="keepDrawing">继续绘画</button><button type="button" @click="discardDrawing">放弃并关闭</button></div>
      <div class="tool-workspace">
        <ImageCompressor v-if="selected.key === 'grid_01'" />
        <DrawingBoard v-else @dirty="dirty = $event" />
      </div>
    </template>
  </dialog>
</template>

<style scoped>
.tools-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; grid-auto-rows: minmax(190px, auto); list-style: none; padding: 0; margin: 0; }
.tool-cell { min-width: 0; min-height: 190px; display: flex; align-items: center; justify-content: center; gap: 12px; border: 1px solid #e0e5d8; border-radius: 15px; background: #fffefa; color: #839775; }
.tool-cell svg { width: 27px; height: 27px; stroke-width: 1.35; flex-shrink: 0; }
.tool-live { color: #36553d; background: #f0f3e9; }
.tool-launch { width: 100%; height: 100%; box-sizing: border-box; display: grid; grid-template-columns: 28px minmax(0, 1fr); grid-template-rows: auto auto 1fr auto; align-items: center; gap: 12px; text-align: left; border: 0; border-radius: inherit; background: transparent; color: inherit; padding: 22px; cursor: pointer; font: inherit; }
.tool-launch:hover { background: #e5ecdd; }
.tool-launch:focus-visible, .tool-close:focus-visible, .tool-controls a:focus-visible { outline: 3px solid #54784a; outline-offset: 3px; }
.tool-brand { font-size: 11px; letter-spacing: .08em; color: #71816a; }
.tool-launch .tool-brand { grid-column: 1 / -1; display: flex; justify-content: space-between; }
.tool-launch strong { font-size: 19px; font-weight: 500; }
.tool-description { grid-column: 1 / -1; align-self: start; font-size: 12px; line-height: 1.8; color: #6d7e63; }
.tool-action { grid-column: 1 / -1; grid-row: 4; font-size: 12px; }
.placeholder-label { font-size: 11px; }
.tool-note { color: #7c8973; font-size: 12px; margin: 18px 0 0; line-height: 1.8; }
.tool-dialog { width: min(1240px, calc(100vw - 32px)); max-width: none; height: min(900px, calc(100dvh - 32px)); max-height: none; box-sizing: border-box; padding: 0; margin: auto; border: 1px solid #d8e1d0; border-radius: 18px; background: #fafbf5; color: #304130; }
.tool-dialog[open] { display: flex; flex-direction: column; }
.tool-dialog::backdrop { background: #172519aa; }
.tool-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 24px 12px; }
.tool-toolbar h2 { font-size: 22px; margin: 4px 0 0; font-weight: 500; }
.tool-controls { display: flex; align-items: center; gap: 18px; }

.tool-close { min-height: 44px; padding: 0 15px; border: 1px solid #d4ddcc; border-radius: 8px; background: #edf1e6; color: #36553d; cursor: pointer; font: inherit; font-size: 13px; }
.tool-instructions { padding: 0 24px; margin: 0 0 8px; font-size: 12px; line-height: 1.7; }
.tool-workspace { flex: 1; min-height: 0; overflow: auto; padding: 12px 24px 24px; }
.tool-exit-confirm { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 12px 24px; background: #fff0d4; font-size: 13px; }
.tool-exit-confirm button { min-height: 38px; padding: 0 12px; border: 1px solid #bda874; border-radius: 7px; background: white; color: #514420; cursor: pointer; }
@media (max-width: 700px) { .tools-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } }
@media (max-width: 540px) { .tools-grid { gap: 10px; } .tool-launch { padding: 16px; gap: 10px; grid-template-columns: 24px minmax(0, 1fr); } .tool-launch svg { width: 23px; height: 23px; } .tool-brand { font-size: 9px; letter-spacing: .04em; } .tool-launch strong { font-size: 17px; } .tool-cell { min-height: 190px; } .tool-dialog { width: 100vw; height: 100dvh; border-radius: 0; border: 0; } .tool-toolbar { padding: 12px 14px; gap: 8px; } .tool-controls { gap: 10px; } .tool-toolbar h2 { font-size: 18px; } .tool-instructions { padding: 0 14px; } .tool-workspace { padding: 8px 14px 18px; } }
</style>
