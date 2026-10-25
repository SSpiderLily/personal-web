<script setup>
import { computed, onMounted, ref } from 'vue'

const props = defineProps({ api: { type: Object, required: true } })
const emit = defineEmits(['unauthenticated'])
const draft = ref([])
const baseline = ref([])
const loading = ref(false)
const saving = ref(false)
const ready = ref(false)
const error = ref('')
const saved = ref(false)
const grid = computed(() => draft.value.filter(item => item.placement === 'grid'))
const floating = computed(() => draft.value.filter(item => item.placement === 'floating'))
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseline.value))
const copy = items => items.map(item => ({ ...item }))

function normalized(value) {
  const keys = new Set()
  const orders = new Set()
  if (!Array.isArray(value?.tools) || value.tools.length !== 10) throw new Error('invalid response')
  const items = value.tools.map(item => {
    const gridKey = /^grid_0[1-9]$/.test(item?.tool_key)
    if ((!gridKey && item?.tool_key !== 'dice') || keys.has(item.tool_key) ||
        item.placement !== (gridKey ? 'grid' : 'floating') || typeof item.is_visible !== 'boolean' ||
        !Number.isInteger(item.sort_order) || (gridKey ? item.sort_order < 0 || item.sort_order > 8 || orders.has(item.sort_order) : item.sort_order !== 0)) {
      throw new Error('invalid response')
    }
    keys.add(item.tool_key)
    if (gridKey) orders.add(item.sort_order)
    return { tool_key: item.tool_key, placement: item.placement, is_visible: item.is_visible, sort_order: item.sort_order }
  })
  return items.sort((a, b) => Number(a.placement !== 'grid') - Number(b.placement !== 'grid') || a.sort_order - b.sort_order)
}
function failure(reason) {
  if (reason?.status === 401) {
    error.value = '登录已失效，请重新登录。'
    emit('unauthenticated')
  } else if (reason?.status === 400) error.value = '工具设置格式不正确，请检查后重试。'
  else if (reason?.status === 403) error.value = '安全验证失败，请刷新页面后重试。'
  else error.value = '工具设置暂时不可用，请稍后重试。'
}
function accept(value) {
  const items = normalized(value)
  baseline.value = copy(items)
  draft.value = copy(items)
  ready.value = true
}
async function load() {
  if (loading.value || saving.value) return
  loading.value = true
  error.value = ''
  try { accept(await props.api.load()) } catch (reason) { failure(reason) }
  finally { loading.value = false }
}
async function save() {
  if (!ready.value || saving.value || loading.value || !dirty.value) return
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    accept(await props.api.save({ tools: copy(draft.value) }))
    saved.value = true
  } catch (reason) { failure(reason) }
  finally { saving.value = false }
}
function reset() {
  if (saving.value) return
  draft.value = copy(baseline.value)
  error.value = ''
}
function move(key, offset) {
  if (saving.value) return
  const items = [...grid.value]
  const index = items.findIndex(item => item.tool_key === key)
  const target = index + offset
  if (index < 0 || target < 0 || target >= items.length) return
  ;[items[index], items[target]] = [items[target], items[index]]
  items.forEach((item, order) => { item.sort_order = order })
  draft.value = [...items, ...floating.value]
  saved.value = false
}
onMounted(load)
</script>

<template>
  <section class="tools-panel" aria-label="小工具设置" :aria-busy="loading || saving">
    <p class="tools-intro">调整工具的显示和顺序。九宫格工具仍为占位，骰子单独悬浮显示。</p>
    <p v-if="loading" role="status">正在加载工具设置…</p>
    <div v-if="error" class="tools-error" role="alert">
      <p>{{ error }}</p>
      <button v-if="!ready" type="button" :disabled="loading" @click="load">重试加载</button>
    </div>
    <template v-if="ready">
      <fieldset :disabled="saving || loading">
        <legend>九宫格工具</legend>
        <ul class="tools-list">
          <li v-for="(item, index) in grid" :key="item.tool_key">
            <span class="tools-name">工具占位 {{ Number(item.tool_key.slice(-2)) }}</span>
            <label><input v-model="item.is_visible" type="checkbox" :aria-label="`${item.tool_key} 显示`" @change="saved = false"> 显示</label>
            <div class="tools-order">
              <button type="button" :aria-label="`${item.tool_key} 上移`" :disabled="index === 0" @click="move(item.tool_key, -1)">上移</button>
              <button type="button" :aria-label="`${item.tool_key} 下移`" :disabled="index === grid.length - 1" @click="move(item.tool_key, 1)">下移</button>
            </div>
          </li>
        </ul>
      </fieldset>
      <fieldset :disabled="saving || loading" class="tools-floating-group">
        <legend>悬浮工具</legend>
        <div v-for="item in floating" :key="item.tool_key" class="tools-floating">
          <span class="tools-name">骰子</span>
          <label><input v-model="item.is_visible" type="checkbox" :aria-label="`${item.tool_key} 显示`" @change="saved = false"> 显示</label>
        </div>
      </fieldset>
      <div class="tools-actions">
        <button type="button" class="tools-save" :disabled="saving || loading || !dirty" @click="save">{{ saving ? '正在保存…' : '保存设置' }}</button>
        <button type="button" :disabled="saving || loading || !dirty" @click="reset">撤销更改</button>
        <span v-if="saved" role="status">已保存</span>
        <span v-else-if="dirty">有未保存的更改</span>
      </div>
    </template>
  </section>
</template>

<style scoped>
.tools-panel { color: var(--admin-ink, #304130); font-size: 13px; }
.tools-intro { margin: 0 0 24px; color: var(--admin-muted, #73806a); line-height: 1.9; }
fieldset { min-width: 0; border: 1px solid var(--admin-line, #dce2d3); border-radius: 12px; padding: 20px; background: #fffefa; }
.tools-floating-group { margin-top: 20px; }
legend { padding: 0 8px; font-weight: 600; }
.tools-list { list-style: none; margin: 0 0 24px; padding: 0; }
.tools-list li, .tools-floating { display: flex; align-items: center; gap: 16px; min-height: 64px; border-bottom: 1px solid #edf0e7; }
.tools-name { flex: 1; min-width: 90px; }
label { display: flex; align-items: center; gap: 5px; min-height: 44px; white-space: nowrap; }
input { accent-color: #3d6041; }
.tools-order { display: flex; gap: 6px; }
button { min-height: 44px; border: 1px solid #dce2d3; border-radius: 6px; background: #f6f7f1; color: #496043; padding: 0 12px; font: inherit; cursor: pointer; }
button:disabled { opacity: .45; cursor: default; }
.tools-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 20px; }
.tools-actions span { color: #68795d; font-size: 12px; }
.tools-save { background: #3d6041; color: white; border-color: #3d6041; }
.tools-error { color: #a33e35; margin-bottom: 20px; }
.tools-error p { line-height: 1.8; }
@media (max-width: 540px) {
  fieldset { padding: 12px; }
  .tools-list li { flex-wrap: wrap; gap: 6px 12px; padding: 10px 0; }
  .tools-order { flex-basis: 100%; }
  .tools-order button { flex: 1; }
}
</style>
