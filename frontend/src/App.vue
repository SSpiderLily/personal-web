<script setup>
import { onBeforeUnmount, onMounted, ref, computed, watch } from 'vue'
import { createVisitCollector } from './statistics/visitCollector.js'
import ProjectContent from './components/ProjectContent.vue'
import { fetchProjects, fetchProject } from './projects/publicProjects.js'
import { projectImageUrl, projectLink } from './projects/projectContent.js'
import DiceGame from './components/DiceGame.vue'
import ToolGrid from './components/ToolGrid.vue'
import { allowPageNavigation } from './tools/navigationGuard.js'
import { usePublicTools } from './tools/publicTools.js'
const { status: toolsStatus, error: toolsError, gridItems, diceVisible, load: loadTools } = usePublicTools()
const profile = ref(null)
const avatarLoadError=ref(false)
watch(()=>profile.value?.avatar_file_id,()=>{avatarLoadError.value=false})
const pages=[{id:'home',label:'首页'},{id:'works',label:'作品'},{id:'notes',label:'记录'},{id:'about',label:'关于'}]
function routeFromHash(){const id=(window.location.hash || '').replace(/^#\/?/,'');return pages.some(p=>p.id===id)?id:'home'}
const page=ref(routeFromHash())
const category=ref('全部')
const categories=['全部','项目','工具','实验']
const displayName=computed(()=>profile.value?.name || '我的个人网站')
const introduction=computed(()=>profile.value?.introduction || '在这里记录学习与思考，也把有趣的想法做成可以使用的作品。')
const skills=computed(()=>profile.value?.skills || [])
const about=computed(()=>({...{
  page_title:'关于我',page_intro:'很高兴，你愿意再多了解一点。',about_heading:'一个放下想法、展示实践的地方。',
  about_body:'在这里整理项目，也为学习记录和小实验留一个位置。',current_heading:'最近的实践',current_project_label:projects.value[0]?.name || '',current_project_url:'/#/works',contact_heading:'找到我',contact_intro:'欢迎交流项目实践。',
},...Object.fromEntries(Object.entries(profile.value?.about_content || {}).filter(([,value])=>value!==''))}))
function focusMain(){document.querySelector?.('main')?.focus()}
function syncRoute(){if(!allowPageNavigation(window,page.value,routeFromHash()))return;detailsDialog.value?.close?.();page.value=routeFromHash();document.title=`${pages.find(p=>p.id===page.value).label} · ${displayName.value}`;window.scrollTo?.({top:0,behavior:'instant'});loadProfile()}
function refreshVisible(){if(document.visibilityState==='visible')loadProfile()}
function workKind(project){return project.category?.includes('实验')?'实验':project.category?.includes('工具')?'工具':'项目'}
const visibleProjects=computed(()=>category.value==='全部'?projects.value:projects.value.filter(p=>workKind(p)===category.value))
function safeLinks(items,contacts){return (Array.isArray(items)?items:[]).filter(item=>{
  if(typeof item?.label!=='string' || typeof item?.url!=='string' || /[\s\\\u0000-\u001f\u007f]/.test(item.url))return false
  if(projectLink(item.url,{}))return true
  if(!contacts)return false
  return /^mailto:[A-Za-z0-9.!#$&'*+/=_`{|}~-]+@[A-Za-z0-9][A-Za-z0-9.-]*$/i.test(item.url)||/^tel:\+?[0-9][0-9().-]*$/i.test(item.url)
})}
const contactLinks=computed(()=>[...safeLinks(profile.value?.contacts,true),...safeLinks(profile.value?.social_links,false)])

const loading = ref(true)
const error = ref('')
const projects = ref([])
const projectsLoading = ref(true)
const projectsError = ref('')
const detailLoading = ref(false)
const detailError = ref('')
const selectedProject = ref(null)
const selectedId = ref(null)
let detailRequest = 0
let alive = true
let visitCollector = null
function recordProjectVisit(event) {
  const id = event?.detail?.project_id
  if (visitCollector && Number.isSafeInteger(id) && id > 0) void visitCollector.project(id)
}
async function loadProjects() {
  projectsLoading.value = true
  projectsError.value = ''
  try { const items = await fetchProjects(); if (alive) projects.value = items }
  catch { if (alive) projectsError.value = '暂时无法加载项目，请稍后重试。' }
  finally { if (alive) projectsLoading.value = false }
}
const detailsDialog = ref(null)
let previousOverflow = ''
async function showProject(project) {
  selectedId.value = project.id
  selectedProject.value = null
  detailError.value = ''
  detailLoading.value = true
  const request = ++detailRequest
  if (!detailsDialog.value.open) {
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    detailsDialog.value.showModal()
  }
  detailsDialog.value.scrollTop = 0
  try {
    const value = await fetchProject(project.id)
    if (!alive || request !== detailRequest || !detailsDialog.value.open) return
    selectedProject.value = value
    window.dispatchEvent(new CustomEvent('project-opened', { detail: { project_id: value.id } }))
  } catch {
    if (alive && request === detailRequest) detailError.value = '项目暂时无法读取，可能已下架。请重试或返回列表。'
  } finally { if (alive && request === detailRequest) detailLoading.value = false }
}
function restoreScroll() {
  detailRequest++
  document.body.style.overflow = previousOverflow
}
function closeOnBackdrop(event) {
  if (event.target === detailsDialog.value) detailsDialog.value.close()
}
onBeforeUnmount(() => {
  window.removeEventListener('hashchange',syncRoute)
  window.removeEventListener('focus',loadProfile)
  document.removeEventListener?.('visibilitychange',refreshVisible)
  window.removeEventListener('project-opened', recordProjectVisit)
  visitCollector?.dispose()
  visitCollector = null
  alive = false
  restoreScroll()
})
let profileRequest=0
async function loadProfile() {
  const request=++profileRequest
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/profile', { signal: AbortSignal.timeout(8000) })
    if (!response.ok) throw new Error('Request failed')
    const value = await response.json()
    if (!value || ['name', 'title', 'introduction'].some(key => typeof value[key] !== 'string') || !Array.isArray(value.skills)) throw new Error('Invalid profile')
    if (alive && request===profileRequest) { profile.value = value; document.title=`${pages.find(p=>p.id===page.value).label} · ${displayName.value}` }
  } catch {
    if(alive && request===profileRequest)error.value = '暂时无法加载个人信息，你仍可以浏览下面的项目。'
  } finally {
    if(alive && request===profileRequest)loading.value = false
  }
}
onMounted(() => {
  window.addEventListener('hashchange',syncRoute)
  window.addEventListener('focus',loadProfile)
  document.addEventListener?.('visibilitychange',refreshVisible)
  if (window.location.pathname === '/') {
    visitCollector = createVisitCollector()
    window.addEventListener('project-opened', recordProjectVisit)
    void visitCollector.website()
  }
  loadProfile()
  loadProjects()
})
</script>

<template>
  <a class="skip-link" href="#main-content" @click.prevent="focusMain">跳到主要内容</a>
  <div class="site-shell">
    <header class="site-header">
      <a class="brand" href="#/home" aria-label="返回首页"><span class="brand-mark" aria-hidden="true">✳</span>{{ displayName }}<span class="brand-dot">.</span></a>
      <nav aria-label="主导航">
        <a v-for="item in pages" :key="item.id" :href="`#/${item.id}`" :class="{active:page === item.id}" :aria-current="page === item.id ? 'page' : undefined">{{ item.label }}<span class="nav-dot" aria-hidden="true"></span></a>
      </nav>
      <a class="header-note" href="#/about">很高兴在这里遇见你 <span aria-hidden="true">↗</span></a>
    </header>

    <main id="main-content" tabindex="-1"><p v-if="loading" class="profile-status" role="status">正在加载个人信息…</p><p v-else-if="error" class="profile-status" role="alert">{{ error }} <button class="retry" @click="loadProfile">重试</button></p>
      <template v-if="page === 'home'">
        <section class="hero" aria-labelledby="hero-title">
          <div class="hero-copy">
            <p class="eyebrow"><span class="tiny-dot"></span> A SMALL CORNER OF THE INTERNET</p>
            <p v-if="profile?.name" class="hello">你好，我是 {{ profile.name }}。</p>
            <h1 v-if="profile?.title" id="hero-title">{{ profile.title }}</h1><h1 v-else id="hero-title">保持好奇，<br>把想法<span class="serif-accent">变成作品。</span><svg class="title-stroke" viewBox="0 0 300 15" aria-hidden="true"><path d="M3 11Q140 -3 295 7" /></svg></h1>
            <p class="hero-intro">{{ introduction }}</p>
            <div class="hero-actions"><a class="button button-primary" href="#/works">探索我的作品 <span aria-hidden="true">↗</span></a><a class="quiet-link" href="#/about">多了解我一点 <span aria-hidden="true">→</span></a></div>
            <div class="hero-footnote"><span class="small-cross" aria-hidden="true">+</span> 学习、实践，再向前一点。<span class="footnote-line"></span></div>
          </div>
          <div class="hero-art" aria-hidden="true">
            <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
            <span class="art-label">IDEAS INTO REALITY</span><span class="art-coordinate">01 — ONGOING</span>
            <div class="art-window"><div class="window-bar"><span><i></i><i></i><i></i></span><span>little things, made with care</span><b>↗</b></div><div class="window-content"><span class="window-kicker">LEARN. BUILD. SHARE.</span><div class="art-flower">✳</div><p>从一个小小的<br><em>想法开始。</em></p><div class="window-bottom"><span>保持好奇，持续创造</span><span>↗</span></div></div></div>
            <span class="floating-tag tag-code">&lt;/&gt; &nbsp; 在实践中学习</span><span class="floating-tag tag-idea"><span>✦</span> 给想法一点空间</span><span class="art-spark">✧</span>
          </div>
        </section>
        <div class="section-divider"><span>一些实践，一些思考</span><span>SCROLL TO EXPLORE <span aria-hidden="true">↓</span></span></div>

        <section class="featured-section" aria-labelledby="featured-heading">
          <div class="section-heading"><div><p class="eyebrow">01 / SELECTED WORK</p><h2 id="featured-heading">想法的落点<span>.</span></h2></div><a class="quiet-link" href="#/works">全部作品 <span aria-hidden="true">↗</span></a></div>
          <p v-if="projectsLoading" class="profile-status" role="status">正在加载项目…</p><p v-else-if="projectsError" class="profile-status" role="alert">{{ projectsError }} <button class="retry" @click="loadProjects">重试</button></p><p v-else-if="!projects.length" class="profile-status">暂未发布项目。</p><div class="featured-layout">
<article v-for="project in projects.slice(0, 3)" :key="project.id" class="feature-project"><button class="project-cover" :aria-label="`查看${project.name}完整详情`" aria-haspopup="dialog" @click="showProject(project)"><div class="cover-heading"><span>{{ project.name }}</span><span>{{ project.category }} ↗</span></div><img v-if="projectImageUrl(project.cover_file_id)" :src="projectImageUrl(project.cover_file_id)" :alt="project.cover_alt" width="1280" height="720"><span v-else class="cover-caption">从一个想法开始。</span><span class="cover-open" aria-hidden="true">↗</span></button><div class="project-info"><div class="project-info-top"><span class="category-label">{{ project.category || '项目' }}</span><span class="muted-meta">{{ project.tech_stack.join(' · ') }}</span></div><button class="project-title" @click="showProject(project)" aria-haspopup="dialog">{{ project.name }} <span aria-hidden="true">↗</span></button><p>{{ project.summary }}</p></div></article>
            <aside class="work-note"><span class="note-symbol" aria-hidden="true">✳</span><p class="eyebrow">ALWAYS IN PROGRESS</p><h3>从好奇出发，<br>在动手中找到答案。</h3><p>这里收集我做过的项目、实用的小工具，以及还在探索中的实验。</p><a class="quiet-link" href="#/works">看看这些尝试 <span aria-hidden="true">↗</span></a><span class="note-index">BUILD / LEARN / REPEAT</span></aside>
          </div>
        </section>
        <section class="home-notes" aria-labelledby="latest-heading"><div class="section-heading"><div><p class="eyebrow">02 / FIELD NOTES</p><h2 id="latest-heading">沿途的记录<span>.</span></h2></div><a class="quiet-link" href="#/notes">全部记录 <span aria-hidden="true">↗</span></a></div><div class="notes-empty"><span class="empty-icon" aria-hidden="true">≡</span><div><h3>留一点空间，给正在发生的思考。</h3><p>这里还没有发布的记录。下一次，带着新的发现见。</p></div><span class="empty-label">TO BE CONTINUED</span></div></section>
        <section class="about-strip"><div><p class="eyebrow">A LITTLE MORE ABOUT ME</p><h2>作品之外，也想认识你。</h2><p>关于我的一些介绍，以及继续交流的入口。</p></div><a class="round-link" href="#/about" aria-label="前往关于页面">↗</a></section>
      </template>

      <template v-else-if="page === 'works'">
        <section class="page-intro"><p class="eyebrow">THE THINGS I MAKE</p><h1>作品<span class="serif-accent">与尝试。</span></h1><p>让想法落地，也为新的可能留一点位置。</p></section>
        <div class="works-toolbar"><div class="filters" role="group" aria-label="作品分类"><button v-for="item in categories" :key="item" :aria-pressed="category === item" :class="{selected:category === item}" @click="category=item">{{ item }}<span v-if="item === '全部'">{{ projects.length + gridItems.filter(item => ['grid_01', 'grid_02'].includes(item.tool_key)).length }}</span></button></div><span class="muted-meta">持续构建中 <span class="tiny-dot"></span></span></div>
        <p v-if="projectsLoading" class="profile-status" role="status">正在加载项目…</p><p v-else-if="projectsError" class="profile-status" role="alert">{{ projectsError }} <button class="retry" @click="loadProjects">重试</button></p><div v-if="visibleProjects.length" class="works-grid">
<article v-for="project in visibleProjects" :key="project.id" class="feature-project"><button class="project-cover" :aria-label="`查看${project.name}完整详情`" aria-haspopup="dialog" @click="showProject(project)"><div class="cover-heading"><span>{{ project.name }}</span><span>{{ project.category }} ↗</span></div><img v-if="projectImageUrl(project.cover_file_id)" :src="projectImageUrl(project.cover_file_id)" :alt="project.cover_alt" width="1280" height="720"><span v-else class="cover-caption">从一个想法开始。</span><span class="cover-open" aria-hidden="true">↗</span></button><div class="project-info"><div class="project-info-top"><span class="category-label">{{ project.category || '项目' }}</span><span class="muted-meta">{{ project.tech_stack.join(' · ') }}</span></div><button class="project-title" @click="showProject(project)" aria-haspopup="dialog">{{ project.name }} <span aria-hidden="true">↗</span></button><p>{{ project.summary }}</p></div></article>

        </div>
        <div v-if="!projectsLoading && !projectsError && !visibleProjects.length && !(diceVisible && (category === '全部' || category === '工具'))" class="page-empty" role="status"><span class="empty-icon" aria-hidden="true">✧</span><h2>这个分类暂时还没有作品。</h2><p>新的实践，会陆续放在这里。</p><button class="button button-outline" @click="category='全部'">浏览全部作品 <span aria-hidden="true">→</span></button></div>
        <section v-if="category==='全部' || category==='工具'" class="utilities-section" :class="{ 'utilities-first': !visibleProjects.length }"><h2>小工具</h2><p v-if="toolsStatus==='loading'" role="status">正在加载小工具…</p><p v-else-if="toolsError" role="alert">{{ toolsError }} <button @click="loadTools">重试</button></p><ToolGrid v-else-if="gridItems.length" :items="gridItems" /><p v-else class="profile-status">暂未展示其他小工具。</p></section><p class="endnote">每一次动手，都是一次新的探索。<span aria-hidden="true">✳</span></p>
      </template>

      <template v-else-if="page === 'notes'">
        <section class="page-intro"><p class="eyebrow">NOTES ALONG THE WAY</p><h1>记录<span class="serif-accent">与思考。</span></h1><p>把学习中的发现、做项目的过程，慢慢整理在这里。</p></section>
        <div class="notes-layout"><div class="page-empty"><span class="empty-icon" aria-hidden="true">≡</span><p class="eyebrow">A BLANK PAGE IS A BEGINNING</p><h2>第一篇，留给值得记录的事。</h2><p>目前还没有发布的文章。<br>你可以先看看已经做出来的作品。</p><a href="#/works" class="button button-outline">去看看作品 <span aria-hidden="true">↗</span></a></div><aside class="notes-aside"><span class="note-symbol" aria-hidden="true">✳</span><h3>记录，也是理解的过程。</h3><p>不急着给出答案，先把问题和发现留下来。</p><span class="note-index">LEARN / THINK / WRITE</span></aside></div>
      </template>

      <template v-else-if="page === 'about'">
        <section class="page-intro"><p class="eyebrow">THE PERSON BEHIND THE WORK</p><h1>{{ about.page_title }}</h1><p>{{ about.page_intro }}</p></section>
        <div class="about-layout">
          <aside class="about-identity"><img v-if="profile?.avatar_file_id && !avatarLoadError" class="identity-art identity-avatar" :src="`/api/files/${profile?.avatar_file_id}`" :alt="`${displayName} 的头像`" width="110" height="110" @error="avatarLoadError=true"><span v-else class="identity-art" aria-hidden="true">✳</span><h2>{{ displayName }}</h2><p>LEARN · BUILD · SHARE</p><div class="skill-tags"><span v-for="(skill,index) in skills" :key="index">{{ skill }}</span></div></aside>
          <div class="about-body">
            <section><p class="eyebrow">01 / HELLO THERE</p><h2>{{ about.about_heading }}</h2><p class="editable-prose">{{ introduction }}</p><p v-if="about.about_body" class="editable-prose">{{ about.about_body }}</p></section>
            <section v-if="about.current_project_label && about.current_project_url"><p class="eyebrow">02 / CURRENTLY EXPLORING</p><h2>{{ about.current_heading }}</h2><a class="about-project-link" :href="about.current_project_url"><span><small>PROJECT IN FOCUS</small>{{ about.current_project_label }}</span><span aria-hidden="true">↗</span></a></section>
            <section><p class="eyebrow">03 / SAY HELLO</p><h2>{{ about.contact_heading }}</h2><p class="editable-prose">{{ about.contact_intro }}</p><div class="contact-links"><a v-for="(contact,index) in contactLinks" :key="index" class="quiet-link" :href="contact.url" rel="noopener noreferrer">{{ contact.label }} <span aria-hidden="true">↗</span></a></div></section>
          </div>
        </div>
      </template>
    </main>

    <footer class="site-footer"><div><a class="footer-brand" href="#/home">保持好奇<span>.</span></a><p>一步一步，把想法变成作品。</p></div><div class="footer-right"><a href="https://github.com/SSpiderLily/Trip_Planner" target="_blank" rel="noopener noreferrer">GitHub ↗</a><a href="#/about">关于与联系 ↗</a><span>© {{ new Date().getFullYear() }} · 认真创造，慢慢生长。</span></div></footer>
  </div>

    <dialog ref="detailsDialog" class="project-dialog" aria-labelledby="detail-title" @close="restoreScroll" @click="closeOnBackdrop">
      <div class="detail-panel">
        <div class="detail-topbar"><span>PROJECT / 项目详情</span><button class="dialog-close" aria-label="关闭项目详情" autofocus @click="detailsDialog.close()">×</button></div>
        <h2 id="detail-title" class="sr-only">{{ selectedProject?.name || '项目详情' }}</h2>
        <div class="detail-body">
          <p v-if="detailLoading" role="status">正在加载项目详情…</p>
          <div v-else-if="detailError" role="alert">{{ detailError }} <button class="retry" @click="showProject({id:selectedId})">重试</button></div>
          <ProjectContent v-else-if="selectedProject" :project="selectedProject" />
        </div>
      </div>
    </dialog>
  <DiceGame v-if="diceVisible" />
</template>
