<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { createVisitCollector } from './statistics/visitCollector.js'
import ProjectContent from './components/ProjectContent.vue'
import PublicProfile from './components/PublicProfile.vue'
import { fetchProjects, fetchProject } from './projects/publicProjects.js'
import { projectImageUrl, projectLink } from './projects/projectContent.js'
import DiceGame from './components/DiceGame.vue'
import ToolGrid from './components/ToolGrid.vue'
import { usePublicTools } from './tools/publicTools.js'
const { status: toolsStatus, error: toolsError, gridItems, diceVisible, load: loadTools } = usePublicTools()
const profile = ref(null)
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
  window.removeEventListener('project-opened', recordProjectVisit)
  visitCollector?.dispose()
  visitCollector = null
  alive = false
  restoreScroll()
})
async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/profile', { signal: AbortSignal.timeout(8000) })
    if (!response.ok) throw new Error('Request failed')
    const value = await response.json()
    if (!value || ['name', 'title', 'introduction'].some(key => typeof value[key] !== 'string') || !Array.isArray(value.skills)) throw new Error('Invalid profile')
    if (alive) profile.value = value
  } catch {
    error.value = '暂时无法加载个人信息，你仍可以浏览下面的项目。'
  } finally {
    loading.value = false
  }
}
onMounted(() => {
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
  <div class="page">
    <header class="site-header">
      <a class="brand" href="#about">我的个人网站<span class="dot">.</span></a>
      <nav aria-label="主导航"><a href="#projects">项目作品</a><a href="#playground">小工具</a><a href="#about">关于我 ↗</a></nav>
    </header>
    <main>
      <section id="about" class="hero">
        <p class="eyebrow">LEARN · BUILD · SHARE</p>
        <PublicProfile v-if="profile" :profile="profile" />
        <a class="text-link hero-project-link" href="#projects">看看我在做什么 <span aria-hidden="true">↓</span></a>
        <p v-if="loading" role="status" class="profile-status">正在加载个人信息…</p>
        <div v-else-if="error" role="alert" class="profile-status">{{ error }} <button class="retry" @click="loadProfile">重试</button></div>
      </section>

      <div class="workspace-layout">
        <section id="projects" class="projects" aria-labelledby="projects-heading">
          <div class="section-title">
            <div><p class="eyebrow">SELECTED PROJECTS</p><h2 id="projects-heading">项目作品<span class="heading-dot">.</span></h2></div>
            <span class="section-note">从想法出发，在实践中完善</span>
          </div>
          <p v-if="projectsLoading" role="status" class="profile-status">正在加载项目…</p>
          <div v-else-if="projectsError" role="alert" class="profile-status">{{ projectsError }} <button class="retry" @click="loadProjects">重试</button></div>
          <p v-else-if="!projects.length" class="profile-status">暂未发布项目。</p>
          <div v-else class="project-list">
            <article v-for="(project, index) in projects" :key="project.id" class="project-card" :aria-labelledby="`${project.id}-heading`">
              <button class="card-open" aria-haspopup="dialog" :aria-label="`查看${project.name}完整详情`" @click="showProject(project)"><span class="sr-only">查看项目详情</span></button>
              <div class="project-preview trip-preview"><img :src="projectImageUrl(project.cover_file_id)" :alt="project.cover_alt" class="project-image" width="1280" height="720" /></div>
              <div class="project-content">
                <div class="project-meta"><span>{{ String(index + 1).padStart(2, '0') }} / {{ project.category }}</span><span class="status"><i aria-hidden="true"></i>{{ projectLink(project.demo_url) ? '可在线体验' : '项目记录' }}</span></div>
                <h3 :id="`${project.id}-heading`">{{ project.name }}</h3>
                <p class="project-description">{{ project.summary }}</p>
                <div class="project-tags" aria-label="项目技术"><span v-for="tag in project.tech_stack" :key="tag">{{ tag }}</span></div>
                <div class="project-actions"><span class="detail-prompt">查看项目详情 <span aria-hidden="true">↗</span></span></div>
              </div>
            </article>
          </div>
          <p class="list-footnote">持续构建，也持续记录。更多作品会慢慢出现在这里。</p>
        </section>
        <aside id="playground" class="playground" aria-labelledby="playground-heading">
          <div class="section-title"><div><p class="eyebrow">LITTLE UTILITIES</p><h2 id="playground-heading">小工具<span class="heading-dot">.</span></h2></div><span class="sidebar-spark" aria-hidden="true">✳</span></div>
          <p v-if="toolsStatus === 'loading'" role="status" class="profile-status">正在加载小工具…</p>
          <div v-else-if="toolsStatus === 'error'" role="alert" class="profile-status">{{ toolsError }} <button class="retry" @click="loadTools">重试</button></div>
          <ToolGrid v-else-if="gridItems.length" :items="gridItems" />
          <p v-else class="profile-status">暂未展示小工具。</p>
        </aside>
      </div>
    </main>
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
    <footer><a class="brand" href="#about">保持好奇<span class="dot">.</span></a><span>一步一步，把想法变成作品。</span><a href="#about">回到顶部 ↑</a></footer>
  </div>
</template>

<style scoped>
.hero-project-link { display: inline-block; margin-top: 26px; }
.hero :deep(.public-profile__title) { font-size: clamp(30px, 3.8vw, 46px); font-weight: 650; line-height: 1.35; color: #283229; margin: 0 0 17px; letter-spacing: -1.6px; }
.hero :deep(.public-profile__introduction) { max-width: 650px; font-size: 14px; color: #71796c; margin: 0; }
.hero :deep(.public-profile h1) { font-size: 16px; margin-bottom: 12px; font-weight: 400; }
.hero :deep(.public-profile__skills) { margin-top: 24px; }
.hero :deep(.public-profile__skills li) { font-size: 10px; border: 1px solid #dce2d5; background: transparent; padding: 5px 11px; color: #7a8572; }
</style>
