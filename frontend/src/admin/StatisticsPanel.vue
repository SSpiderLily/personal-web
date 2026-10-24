<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { parseStatistics } from '../statistics/statisticsModel.js'

const props = defineProps({ api: { type: Object, required: true } })
const emit = defineEmits(['unauthenticated'])
const days = ref(7)
const data = ref(null)
const loading = ref(false)
const error = ref('')
let generation = 0
let disposed = false

async function load() {
  if (disposed) return
  const request = ++generation
  const requestedDays = days.value
  data.value = null
  error.value = ''
  loading.value = true
  try {
    const value = await props.api.load(requestedDays)
    if (disposed || request !== generation) return
    data.value = parseStatistics(value, requestedDays)
  } catch (reason) {
    if (disposed || request !== generation) return
    if (reason?.status === 401) {
      error.value = '登录已失效，请重新登录。'
      emit('unauthenticated')
    } else if (reason?.status === 403) {
      error.value = '安全验证失败，请重试加载。'
    } else error.value = '访问统计暂时不可用，请稍后重试。'
  } finally {
    if (!disposed && request === generation) loading.value = false
  }
}
function selectDays(value) {
  if (value === days.value) return
  days.value = value
  return load()
}
onMounted(load)
onBeforeUnmount(() => { disposed = true; generation++ })
</script>

<template>
  <section class="statistics-panel" aria-label="访问统计" :aria-busy="loading">
    <div class="statistics-actions" role="group" aria-label="统计区间">
      <button type="button" :aria-pressed="days === 7" @click="selectDays(7)">近7天</button>
      <button type="button" :aria-pressed="days === 30" @click="selectDays(30)">近30天</button>
      <button type="button" :disabled="loading" @click="load">刷新</button>
    </div>
    <p class="statistics-intro">人数按同一匿名浏览器在整个区间内独立去重，不是浏览次数。管理员访问和预览不计入统计；各项目人数不能相加作为网站人数。</p>
    <p v-if="loading" role="status">正在加载访问统计…</p>
    <div v-if="error" class="statistics-error" role="alert">
      <p>{{ error }}</p>
      <button type="button" :disabled="loading" @click="load">重试加载</button>
    </div>
    <template v-if="data">
      <p class="statistics-period">{{ data.start_date }} 至 {{ data.end_date }}（北京时间，Asia/Shanghai，含首尾日期）</p>
      <div class="statistics-card">
        <h3>网站访问人数</h3>
        <p class="statistics-count">{{ data.website_visitors }}</p>
      </div>
      <table>
        <caption>项目浏览人数</caption>
        <thead><tr><th scope="col">项目</th><th scope="col">人数</th></tr></thead>
        <tbody>
          <tr v-for="item in data.projects" :key="item.project_id">
            <th scope="row">{{ item.name || `未命名项目 #${item.project_id}` }}</th>
            <td>{{ item.visitors }}</td>
          </tr>
          <tr v-if="!data.projects.length"><td colspan="2" class="statistics-empty">暂无项目浏览统计。</td></tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<style scoped>
.statistics-panel { min-width: 0; color: var(--admin-ink, #304130); font-size: 13px; }
.statistics-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
button { min-height: 44px; padding: 0 12px; border: 1px solid var(--admin-line, #dce2d3); border-radius: 6px; background: #f6f7f1; color: #496043; font: inherit; cursor: pointer; }
button[aria-pressed="true"] { background: #3d6041; border-color: #3d6041; color: white; }
button:disabled { opacity: .45; cursor: default; }
button:focus-visible { outline: 3px solid #68795d; outline-offset: 3px; }
.statistics-intro, .statistics-period { color: var(--admin-muted, #73806a); line-height: 1.9; overflow-wrap: anywhere; }
.statistics-card { margin: 20px 0; padding: 20px; border: 1px solid var(--admin-line, #dce2d3); border-radius: 12px; background: #fffefa; }
h3 { margin: 0; font-size: 13px; font-weight: 600; }
.statistics-count { margin: 12px 0 0; font-size: 32px; font-weight: 600; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; background: #fffefa; }
caption { padding: 12px 0; text-align: left; font-weight: 600; }
th, td { padding: 14px 12px; border-bottom: 1px solid var(--admin-line, #dce2d3); text-align: left; overflow-wrap: anywhere; }
th { font-weight: 600; }
th:last-child, td:last-child { width: 32%; text-align: right; }
.statistics-empty { color: var(--admin-muted, #73806a); text-align: center !important; }
.statistics-error { margin: 20px 0; color: #a33e35; line-height: 1.8; }
@media (max-width: 540px) { .statistics-card { padding: 16px; } th, td { padding: 12px 8px; } }
</style>
