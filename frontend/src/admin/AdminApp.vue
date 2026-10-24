<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { createAdminApi, AdminApiError } from './adminApi.js'
import ToolsPanel from './ToolsPanel.vue'
import ProjectsPanel from './ProjectsPanel.vue'
import ProfilePanel from './ProfilePanel.vue'
import StatisticsPanel from './StatisticsPanel.vue'

const props = defineProps({ api: { type: Object, default: () => createAdminApi() } })
const phase = ref('checking')
const session = ref(null)
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
const overviewReady = ref(false)
const selected = ref('projects')
const visited = ref(new Set(['projects']))
let alive = true
let authGeneration = 0
function isCurrent(generation) { return alive && generation === authGeneration }
function beginOperation() {
  busy.value = true
  return ++authGeneration
}
const toolModuleApi = {
  load: () => props.api.tools(),
  save: value => props.api.saveTools(value, session.value?.csrf_token),
}
const projectModuleApi = {
  list: () => props.api.projects(), get: id => props.api.project(id),
  create: value => props.api.createProject(value, session.value?.csrf_token),
  save: (id, value) => props.api.saveProject(id, value, session.value?.csrf_token),
  publish: id => props.api.publishProject(id, session.value?.csrf_token),
  archive: id => props.api.archiveProject(id, session.value?.csrf_token),
  reorder: ids => props.api.reorderProjects(ids, session.value?.csrf_token),
  upload: file => props.api.uploadFile(file, session.value?.csrf_token),
}
const statisticsModuleApi = { load: days => props.api.statistics(days) }
const profileModuleApi = {
  load: () => props.api.profile(), save: value => props.api.saveProfile(value, session.value?.csrf_token),
  upload: file => props.api.uploadFile(file, session.value?.csrf_token),
}
function moduleUnauthenticated() { failure(new AdminApiError('unauthenticated', 401)) }
const modules = [
  { id: 'projects', label: '项目管理', index: '01', description: '维护项目内容、图文详情和展示顺序。', scope: '项目列表、草稿、预览、发布与下架', dependency: '等待项目管理和图片上传接入。' },
  { id: 'statistics', label: '访问统计', index: '02', description: '了解网站和项目的访问人数。', scope: '近 7 天、近 30 天的网站人数与项目浏览人数', dependency: '近7/30天按匿名浏览器独立去重，管理员与预览不计入。' },
  { id: 'content', label: '网站内容', index: '03', description: '让个人介绍与联系方式保持更新。', scope: '姓名、头像、个人简介、联系方式和社交账号', dependency: '等待个人资料接口和图片上传接入。' },
  { id: 'tools', label: '小工具管理', index: '04', description: '安排九宫格工具与独立骰子的展示。', scope: '九宫格展示、排序与独立骰子开关', dependency: '等待工具设置接口接入。' },
]
const current = computed(() => modules.find(module => module.id === selected.value))
function clearSession({ preservePassword = false } = {}) {
  ++authGeneration
  busy.value = false
  session.value = null
  if (!preservePassword) password.value = ''
  overviewReady.value = false
  selected.value = 'projects'
  visited.value = new Set(['projects'])
  phase.value = 'anonymous'
}
function failure(reason) {
  if (!alive) return
  if (reason?.status === 401 || reason?.code === 'unauthenticated') clearSession()
  error.value = reason instanceof AdminApiError ? reason.message : '后台暂时不可用，请稍后重试。'
}
async function readOverview(generation) {
  try {
    await props.api.overview()
    if (isCurrent(generation)) overviewReady.value = true
  } catch (reason) { if (isCurrent(generation)) failure(reason) }
}
async function restoreSession() {
  if (busy.value) return
  const wasAnonymous = phase.value === 'anonymous'
  const wasAuthenticated = phase.value === 'authenticated'
  const generation = beginOperation()
  if (!wasAnonymous && !wasAuthenticated) phase.value = 'checking'
  error.value = ''
  try {
    const value = await props.api.session()
    if (!isCurrent(generation)) return
    if (!value.authenticated) clearSession({ preservePassword: wasAnonymous })
    else {
      session.value = value
      phase.value = 'authenticated'
      password.value = ''
      if (!wasAuthenticated || !overviewReady.value) await readOverview(generation)
    }
  } catch (reason) {
    if (!isCurrent(generation)) return
    if (!wasAuthenticated) {
      clearSession()
      phase.value = 'unavailable'
    }
    failure(reason)
  } finally { if (isCurrent(generation)) busy.value = false }
}
async function login() {
  if (busy.value) return
  const generation = beginOperation()
  error.value = ''
  try {
    const value = await props.api.login(username.value.trim(), password.value, session.value?.csrf_token)
    if (!isCurrent(generation)) return
    session.value = value
    phase.value = 'authenticated'
    password.value = ''
    await readOverview(generation)
  } catch (reason) { if (isCurrent(generation)) failure(reason) }
  finally { if (isCurrent(generation)) { password.value = ''; busy.value = false } }
}
async function logout() {
  if (busy.value || !session.value) return
  const generation = beginOperation()
  error.value = ''
  try {
    await props.api.logout(session.value.csrf_token)
    if (isCurrent(generation)) clearSession()
  } catch (reason) { if (isCurrent(generation)) failure(reason) }
  finally { if (isCurrent(generation)) busy.value = false }
}
async function refreshOverview() {
  if (busy.value || !session.value) return
  const generation = beginOperation()
  error.value = ''
  try { await readOverview(generation) }
  finally { if (isCurrent(generation)) busy.value = false }
}
async function selectModule(id) {
  if (busy.value || !modules.some(module => module.id === id)) return
  visited.value = new Set([...visited.value, id])
  selected.value = id
  await refreshOverview()
}
function onFocus() { if (!busy.value) restoreSession() }
onMounted(() => {
  restoreSession()
  if (typeof window !== 'undefined') window.addEventListener('focus', onFocus)
})
onBeforeUnmount(() => {
  alive = false
  if (typeof window !== 'undefined') window.removeEventListener('focus', onFocus)
})
</script>

<template>
  <div class="admin-page">
    <header class="admin-topbar">
      <a class="admin-brand" href="/">我的个人网站<span>.</span></a>
      <span class="admin-topbar-label">管理后台</span>
      <a class="admin-public-link" href="/">查看公开网站 ↗</a>
    </header>

    <main v-if="phase !== 'authenticated'" class="admin-login">
      <section class="admin-login-intro" aria-labelledby="admin-login-title">
        <p class="admin-eyebrow">PERSONAL WEBSITE / ADMIN</p>
        <h1 id="admin-login-title">管理员登录<span>.</span></h1>
        <p>一个安静的空间，<br />打理作品与个人网站。</p>
        <div class="admin-stage-note"><span>个人管理</span> 使用终端初始化的管理员账号</div>
      </section>
      <section class="admin-login-card" aria-label="登录表单" :aria-busy="busy">
        <p class="admin-badge">仅限管理员</p>
        <template v-if="phase === 'checking'">
          <h2>正在检查登录状态</h2>
          <p class="admin-muted" role="status">请稍候…</p>
        </template>
        <template v-else-if="phase === 'unavailable'">
          <h2>暂时无法连接后台</h2>
          <p class="admin-error" role="alert">{{ error }}</p>
          <button class="admin-primary admin-retry" type="button" @click="restoreSession">重试连接</button>
        </template>
        <template v-else>
          <h2>欢迎回来</h2>
          <p id="admin-login-help" class="admin-muted">登录后管理个人网站。尚未创建账号时，请先在终端完成管理员初始化。</p>
          <p v-if="error" class="admin-error" role="alert">{{ error }}</p>
          <form aria-describedby="admin-login-help" @submit.prevent="login">
            <label for="admin-account">管理员账号</label>
            <input id="admin-account" v-model="username" name="username" type="text" autocomplete="username" placeholder="输入管理员账号" maxlength="64" required :disabled="busy" />
            <label for="admin-password">密码</label>
            <input id="admin-password" v-model="password" name="password" type="password" autocomplete="current-password" placeholder="输入密码" maxlength="128" required :disabled="busy" />
            <button class="admin-primary" type="submit" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button>
          </form>
          <p class="admin-form-footnote">会话由服务端验证。请在自己的设备上登录，使用后及时退出。</p>
        </template>
      </section>
    </main>

    <div v-else class="admin-workspace">
      <aside class="admin-sidebar">
        <p class="admin-eyebrow">WORKSPACE</p>
        <p class="admin-sidebar-title">网站管理</p>
        <nav class="admin-nav" aria-label="后台模块导航">
          <button v-for="module in modules" :key="module.id" type="button" :class="{ 'is-current': selected === module.id }" :aria-current="selected === module.id ? 'page' : undefined" :disabled="busy" @click="selectModule(module.id)">{{ module.label }}</button>
        </nav>
        <div class="admin-session">
          <span class="admin-session-dot" aria-hidden="true"></span>
          <p>{{ session.admin.username }}<small>管理员 · 服务端会话</small></p>
          <button type="button" class="admin-exit" :disabled="busy" @click="logout">{{ busy ? '请稍候…' : '退出登录' }}</button>
        </div>
      </aside>
      <main class="admin-content" :aria-busy="busy">
        <div class="admin-demo-banner"><strong>后台已连接</strong><span>项目、统计、网站内容与小工具使用真实接口。切换模块会保留尚未保存的编辑。</span></div>
        <div v-if="error" class="admin-error-panel" role="alert">
          <p>{{ error }}</p>
          <button type="button" :disabled="busy" @click="restoreSession">重试</button>
        </div>
        <section v-if="overviewReady" :aria-labelledby="'admin-module-title'" class="admin-module">
          <p class="admin-eyebrow">{{ current.index }} / WEBSITE MANAGEMENT</p>
          <h1 id="admin-module-title">{{ current.label }}</h1>
          <p class="admin-module-description">{{ current.description }}</p>
          <ProjectsPanel v-if="visited.has('projects')" v-show="selected === 'projects'" :api="projectModuleApi" @unauthenticated="moduleUnauthenticated" />
          <ProfilePanel v-if="visited.has('content')" v-show="selected === 'content'" :api="profileModuleApi" @unauthenticated="moduleUnauthenticated" />
          <ToolsPanel v-if="visited.has('tools')" v-show="selected === 'tools'" :api="toolModuleApi" @unauthenticated="moduleUnauthenticated" />
          <StatisticsPanel v-if="visited.has('statistics')" v-show="selected === 'statistics'" :api="statisticsModuleApi" @unauthenticated="moduleUnauthenticated" />
        </section>
        <p v-else-if="!error" class="admin-muted" role="status">正在读取后台入口…</p>
      </main>
    </div>
    <footer class="admin-footer">一步一步，把想法变成作品。<span>个人网站管理后台</span></footer>
  </div>
</template>

<style scoped>
:global(body) { margin: 0; }
.admin-page { --admin-ink: #28382f; --admin-muted: #708076; --admin-line: #dbe3d7; --admin-green: #3d6045; min-height: 100dvh; background: #f6f7f2; color: var(--admin-ink); font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif; -webkit-font-smoothing: antialiased; display: flex; flex-direction: column; }
.admin-page *, .admin-page *::before, .admin-page *::after { box-sizing: border-box; }
.admin-page a { text-decoration: none; color: inherit; }
.admin-page button, .admin-page input { font: inherit; }
.admin-page button { cursor: pointer; }
.admin-page button:disabled, .admin-page input:disabled { cursor: not-allowed; }
.admin-page a:focus-visible, .admin-page button:focus-visible { outline: 3px solid #7c9b6b; outline-offset: 4px; }
.admin-topbar { display: flex; align-items: center; gap: 28px; min-height: 86px; padding: 20px 5vw; border-bottom: 1px solid var(--admin-line); }
.admin-brand { font-weight: 700; font-size: 18px; white-space: nowrap; }
.admin-brand span, .admin-login h1 span { color: #789369; }
.admin-topbar-label, .admin-public-link { font-size: 12px; color: var(--admin-muted); }
.admin-public-link { margin-left: auto; }
.admin-login { display: grid; grid-template-columns: 1fr 410px; gap: 70px; align-items: center; width: min(960px, 90%); margin: auto; padding: 72px 0; flex: 1; }
.admin-eyebrow { font-size: 10px; font-weight: 600; letter-spacing: 1.8px; color: #75886c; margin: 0 0 22px; }
.admin-page h1 { margin: 0; font-size: clamp(28px, 3vw, 38px); font-weight: 650; letter-spacing: -1px; line-height: 1.4; }
.admin-login-intro > p:not(.admin-eyebrow) { font-size: 16px; color: var(--admin-muted); line-height: 2; margin: 24px 0; }
.admin-stage-note { margin-top: 48px; font-size: 11px; color: var(--admin-muted); line-height: 1.8; }
.admin-stage-note span { display: inline-block; border: 1px solid var(--admin-line); border-radius: 20px; padding: 3px 10px; margin-right: 8px; }
.admin-login-card { padding: 32px; background: #fffefa; border: 1px solid var(--admin-line); border-radius: 16px; box-shadow: 0 12px 40px #38573b05; }
.admin-badge { display: inline-block; margin: 0 0 16px; padding: 5px 9px; border-radius: 4px; background: #edf1e6; color: #60764f; font-size: 10px; font-weight: 600; }
.admin-page h2 { font-size: 19px; line-height: 1.5; margin: 0 0 10px; font-weight: 600; }
.admin-muted { font-size: 12px; color: var(--admin-muted); line-height: 1.9; }
.admin-login-card form { display: flex; flex-direction: column; margin-top: 24px; }
.admin-login-card label { font-size: 12px; margin: 0 0 8px; }
.admin-login-card input { width: 100%; min-height: 44px; padding: 12px; border: 1px solid var(--admin-line); border-radius: 6px; background: #f5f6f0; color: var(--admin-muted); margin-bottom: 20px; font-size: 12px; opacity: 1; }
.admin-login-card input::placeholder { color: #8a9486; }
.admin-error { color: #a33e35; font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
.admin-retry { width: 100%; }
.admin-error-panel { padding: 12px 16px; margin-top: 18px; border: 1px solid #dfbdb6; border-radius: 8px; color: #a33e35; font-size: 12px; }
.admin-error-panel button { background: transparent; border: 0; color: inherit; text-decoration: underline; min-height: 36px; }
.admin-primary { min-height: 44px; border: 0; border-radius: 6px; background: var(--admin-green); color: #fff; font-size: 12px; }
.admin-primary:hover:not(:disabled) { background: #2e4e35; }
.admin-primary:disabled { background: #dfe5d9; color: #6d7c67; }
.admin-form-footnote { margin: 18px 0 0; font-size: 10px; line-height: 1.8; color: var(--admin-muted); }
.admin-workspace { flex: 1; display: grid; grid-template-columns: 230px minmax(0, 1fr); width: min(1280px, 100%); margin: 0 auto; }
.admin-sidebar { padding: 40px 26px; border-right: 1px solid var(--admin-line); display: flex; flex-direction: column; }
.admin-sidebar .admin-eyebrow { margin-bottom: 10px; }
.admin-sidebar-title { margin: 0 0 30px; font-size: 19px; font-weight: 600; }
.admin-nav { display: grid; gap: 7px; }
.admin-nav button { border: 0; text-align: left; min-height: 44px; border-radius: 6px; background: transparent; color: var(--admin-muted); padding: 12px 14px; font-size: 13px; }
.admin-nav button:hover { background: #edf0e7; }
.admin-nav .is-current { background: #e6ecdd; color: var(--admin-green); font-weight: 600; }
.admin-session { display: grid; grid-template-columns: 6px 1fr; column-gap: 8px; margin-top: auto; padding-top: 64px; }
.admin-session-dot { margin-top: 6px; width: 6px; height: 6px; background: #8a9b70; border-radius: 50%; }
.admin-session p { margin: 0; font-size: 12px; }
.admin-session small { display: block; margin-top: 7px; font-size: 10px; line-height: 1.8; color: var(--admin-muted); }
.admin-exit { grid-column: 2; justify-self: start; border: 0; background: none; color: var(--admin-green); padding: 10px 0 0; font-size: 12px; min-height: 44px; }
.admin-content { min-width: 0; padding: 32px 40px 56px; }
.admin-demo-banner { display: flex; gap: 14px; padding: 14px 18px; border: 1px solid #dce4cc; border-radius: 8px; background: #eef2e6; color: #61704f; font-size: 11px; line-height: 1.8; }
.admin-demo-banner strong { white-space: nowrap; font-weight: 600; }
.admin-module { padding-top: 40px; }
.admin-module .admin-eyebrow { margin-bottom: 12px; }
.admin-module h1 { font-size: 29px; }
.admin-module-description { font-size: 13px; line-height: 1.8; color: var(--admin-muted); margin: 10px 0 30px; }
.admin-pending { display: flex; align-items: center; flex-direction: column; min-height: 310px; justify-content: center; padding: 32px 24px; background: #fffefa; border: 1px dashed #ccd7c2; border-radius: 12px; text-align: center; }
.admin-pending-mark { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 50%; background: #f0f3e9; color: #8a9c77; font-size: 23px; margin-bottom: 18px; }
.admin-pending .admin-badge { margin-bottom: 12px; }
.admin-pending h2 { font-size: 18px; }
.admin-pending > p:not(.admin-badge) { margin: 5px 0; font-size: 12px; line-height: 1.9; color: var(--admin-muted); }
.admin-module-note { margin: 18px 0 0; font-size: 11px; line-height: 1.8; color: var(--admin-muted); }
.admin-footer { display: flex; gap: 16px; justify-content: space-between; border-top: 1px solid var(--admin-line); padding: 22px 5vw; font-size: 10px; color: var(--admin-muted); }
@media (max-width: 760px) {
  .admin-topbar { min-height: 72px; gap: 14px; padding: 20px; }
  .admin-topbar-label { display: none; }
  .admin-brand { font-size: 16px; }
  .admin-public-link { font-size: 11px; }
  .admin-login { grid-template-columns: minmax(0, 1fr); width: min(440px, calc(100% - 40px)); gap: 28px; padding: 36px 0 44px; }
  .admin-login-intro > p:not(.admin-eyebrow) { font-size: 14px; margin: 15px 0; }
  .admin-stage-note { margin-top: 16px; }
  .admin-login-card { padding: 26px; }
  .admin-workspace { grid-template-columns: minmax(0, 1fr); }
  .admin-sidebar { padding: 22px 20px 16px; border-right: 0; border-bottom: 1px solid var(--admin-line); }
  .admin-sidebar > .admin-eyebrow, .admin-sidebar-title { display: none; }
  .admin-nav { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
  .admin-nav button { text-align: center; font-size: 12px; }
  .admin-session { display: flex; align-items: center; gap: 8px; padding-top: 16px; }
  .admin-session-dot { margin-top: 0; flex-shrink: 0; }
  .admin-session p { font-size: 11px; }
  .admin-session small { display: none; }
  .admin-exit { margin-left: auto; padding: 8px; font-size: 11px; }
  .admin-content { padding: 22px 20px 36px; }
  .admin-demo-banner { display: block; padding: 12px 14px; }
  .admin-demo-banner strong { display: block; margin-bottom: 4px; }
  .admin-module { padding-top: 28px; }
  .admin-module h1 { font-size: 26px; }
  .admin-pending { min-height: 290px; padding: 28px 18px; }
  .admin-footer { flex-wrap: wrap; padding: 20px; gap: 10px; }
}
</style>
