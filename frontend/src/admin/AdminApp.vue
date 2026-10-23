<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ demoEnabled: { type: Boolean, default: false } })
// Preview state is deliberately in memory. It is never an authentication credential.
const previewActive = ref(false)
const selected = ref('projects')
const modules = [
  { id: 'projects', label: '项目管理', index: '01', description: '维护项目内容、图文详情和展示顺序。', scope: '项目列表、草稿、预览、发布与下架', dependency: '等待真实登录、项目接口和图片上传接入。' },
  { id: 'statistics', label: '访问统计', index: '02', description: '了解网站和项目的访问人数。', scope: '近 7 天、近 30 天的网站人数与项目浏览人数', dependency: '等待匿名访问记录和去重查询接口接入。' },
  { id: 'content', label: '网站内容', index: '03', description: '让个人介绍与联系方式保持更新。', scope: '姓名、头像、个人简介、联系方式和社交账号', dependency: '等待个人资料接口和图片上传接入。' },
  { id: 'tools', label: '小工具管理', index: '04', description: '安排九宫格工具与独立骰子的展示。', scope: '九宫格展示、排序与独立骰子开关', dependency: '等待工具设置接口接入。' },
]
const current = computed(() => modules.find(module => module.id === selected.value))
function enterPreview() {
  if (props.demoEnabled) previewActive.value = true
}
function exitPreview() {
  previewActive.value = false
  selected.value = 'projects'
}
</script>

<template>
  <div class="admin-page">
    <header class="admin-topbar">
      <a class="admin-brand" href="/">我的个人网站<span>.</span></a>
      <span class="admin-topbar-label">管理后台 · 页面准备</span>
      <a class="admin-public-link" href="/">查看公开网站 ↗</a>
    </header>

    <main v-if="!previewActive" class="admin-login">
      <section class="admin-login-intro" aria-labelledby="admin-login-title">
        <p class="admin-eyebrow">PERSONAL WEBSITE / ADMIN</p>
        <h1 id="admin-login-title">管理员登录<span>.</span></h1>
        <p>一个安静的空间，<br />打理作品与个人网站。</p>
        <div class="admin-stage-note"><span>阶段 A</span> 登录页、导航与布局预览</div>
      </section>
      <section class="admin-login-card" aria-label="登录表单">
        <p class="admin-badge">{{ demoEnabled ? '仅限本地演示' : '页面准备中' }}</p>
        <h2>{{ demoEnabled ? '预览后台布局' : '真实登录尚未接入' }}</h2>
        <p id="admin-login-help" class="admin-muted">{{ demoEnabled ? '请勿输入真实密码。演示无需账号和密码，不连接后台，也不修改网站内容。' : '后台当前仅完成页面准备，暂不能登录或管理网站内容。' }}</p>
        <form autocomplete="off" aria-describedby="admin-login-help" @submit.prevent="enterPreview">
          <label for="admin-account">管理员账号</label>
          <input id="admin-account" type="text" placeholder="真实登录接入后填写" disabled />
          <label for="admin-password">密码</label>
          <input id="admin-password" type="password" placeholder="演示模式无需密码" disabled />
          <button v-if="demoEnabled" class="admin-primary" type="submit">进入本地演示</button>
          <button v-else class="admin-primary" type="submit" disabled>登录暂未开放</button>
        </form>
        <p class="admin-form-footnote">{{ demoEnabled ? '演示会话只保留在当前页面，刷新或退出即清除。' : '正式登录与会话验证将在下一阶段接入。' }}</p>
      </section>
    </main>

    <div v-else class="admin-workspace">
      <aside class="admin-sidebar">
        <p class="admin-eyebrow">WORKSPACE</p>
        <p class="admin-sidebar-title">网站管理</p>
        <nav class="admin-nav" aria-label="后台模块导航">
          <button v-for="module in modules" :key="module.id" type="button" :class="{ 'is-current': selected === module.id }" :aria-current="selected === module.id ? 'page' : undefined" @click="selected = module.id">{{ module.label }}</button>
        </nav>
        <div class="admin-session">
          <span class="admin-session-dot" aria-hidden="true"></span>
          <p>本地演示会话<small>无管理员权限 · 刷新即退出</small></p>
          <button type="button" class="admin-exit" @click="exitPreview">退出演示</button>
        </div>
      </aside>
      <main class="admin-content">
        <div class="admin-demo-banner" role="status"><strong>本地演示</strong><span>仅预览页面与导航，未登录真实后台。所有模块尚未接入，不读取或保存业务数据。</span></div>
        <section :aria-labelledby="'admin-module-title'" class="admin-module">
          <p class="admin-eyebrow">{{ current.index }} / WEBSITE MANAGEMENT</p>
          <h1 id="admin-module-title">{{ current.label }}</h1>
          <p class="admin-module-description">{{ current.description }}</p>
          <div class="admin-pending">
            <div class="admin-pending-mark" aria-hidden="true">＋</div>
            <p class="admin-badge">尚未接入</p>
            <h2>这里将用于{{ current.label }}</h2>
            <p>{{ current.scope }}</p>
            <p class="admin-muted">{{ current.dependency }}</p>
          </div>
          <p class="admin-module-note">当前为页面准备，暂不提供编辑和保存操作。</p>
        </section>
      </main>
    </div>
    <footer class="admin-footer">一步一步，把想法变成作品。<span>后台页面准备 · 阶段 A</span></footer>
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
