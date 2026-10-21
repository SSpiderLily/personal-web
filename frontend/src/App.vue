<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import tripPreview from './assets/trip-preview.png'
import DiceGame from './components/DiceGame.vue'
const profile = ref(null)
const loading = ref(true)
const error = ref('')
// Development links to the separately running local project.
const tripAvailable = true
const tripUrl = import.meta.env.VITE_TRIP_DEMO_URL
  || (import.meta.env.MODE === 'development' ? 'http://127.0.0.1:5173/' : '/trip/')
const projects = [{
  id: 'trip-planner',
  name: '漫游 · 智能旅行助手',
  category: 'AI 应用',
  summary: '输入目的地、时间和偏好，将旅行想法整理成可编辑的行程。结合地图与交通参考，让每天的安排更清楚。',
  tags: ['Vue 3', 'FastAPI', '多智能体', '高德地图'],
  preview: tripPreview,
  previewAlt: '漫游旅行助手实际首页截图：旅行需求填写页面',
  description: [
    '漫游是一个基于多智能体的旅行规划项目。你可以填写目的地、出行日期和个人偏好，也可以补充预算及已订酒店。旅行助手结合这些需求，查询地点、天气和路线信息，整理成按天组织的旅行方案。',
    '在行程预览中，你可以查看景点、餐饮、住宿和交通参考，调整地点顺序、删除不想去的地方，或搜索并加入新的地点。行程支持按日期导出为图片，并保存或还原上次成功保存的结果。',
    '前端使用 Vue 3，后端使用 FastAPI。多智能体分别收集景点、餐饮和住宿信息，高德地图提供地点与路线参考。价格、天气或交通信息不完整时，页面会保留缺项提示；推荐内容不代表实时房价、房态或营业承诺。',
  ],
  features: ['按目的地、日期和偏好生成多日行程', '在地图上查看地点与相邻交通参考', '调整顺序、删除地点、搜索并加入新地点', '逐日导出图片，保存和还原行程'],
  sourceUrl: 'https://github.com/SSpiderLily/Trip_Planner',
  demoUrl: tripUrl,
}]
const selectedProject = ref(projects[0])
const detailsDialog = ref(null)
let previousOverflow = ''
function showProject(project) {
  selectedProject.value = project
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  detailsDialog.value.showModal()
  detailsDialog.value.scrollTop = 0
}
function restoreScroll() {
  document.body.style.overflow = previousOverflow
}
function closeOnBackdrop(event) {
  if (event.target === detailsDialog.value) detailsDialog.value.close()
}
onBeforeUnmount(restoreScroll)
async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/profile', { signal: AbortSignal.timeout(8000) })
    if (!response.ok) throw new Error('Request failed')
    profile.value = await response.json()
  } catch {
    error.value = '暂时无法加载个人信息，你仍可以浏览下面的项目。'
  } finally {
    loading.value = false
  }
}
onMounted(loadProfile)
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
        <p v-if="profile && profile.name !== '你的名字'" class="name">你好，我是 {{ profile.name }}</p>
        <h1>{{ profile?.title || '保持好奇，认真创造。' }}</h1>
        <p class="intro">{{ profile && !profile.introduction.includes('初版默认内容') ? profile.introduction : '在这里记录学习与思考，也把有趣的想法做成可以使用的作品。' }}</p>
        <div class="hero-bottom"><a class="text-link" href="#projects">看看我在做什么 <span aria-hidden="true">↓</span></a><div class="tags"><span v-for="skill in (profile?.skills || ['Python', 'FastAPI', 'Vue 3'])" :key="skill">{{ skill }}</span></div></div>
        <p v-if="loading" role="status" class="profile-status">正在加载个人信息…</p>
        <div v-else-if="error" role="alert" class="profile-status">{{ error }} <button class="retry" @click="loadProfile">重试</button></div>
      </section>

      <div class="workspace-layout">
        <section id="projects" class="projects" aria-labelledby="projects-heading">
          <div class="section-title">
            <div><p class="eyebrow">SELECTED PROJECTS</p><h2 id="projects-heading">项目作品<span class="heading-dot">.</span></h2></div>
            <span class="section-note">从想法出发，在实践中完善</span>
          </div>
          <div class="project-list">
            <article v-for="(project, index) in projects" :key="project.id" class="project-card" :aria-labelledby="`${project.id}-heading`">
              <button class="card-open" aria-haspopup="dialog" :aria-label="`查看${project.name}完整详情`" @click="showProject(project)"><span class="sr-only">查看项目详情</span></button>
              <div class="project-preview trip-preview"><img :src="project.preview" :alt="project.previewAlt" class="project-image" width="1280" height="720" /></div>
              <div class="project-content">
                <div class="project-meta"><span>{{ String(index + 1).padStart(2, '0') }} / {{ project.category }}</span><span class="status"><i aria-hidden="true"></i>{{ tripAvailable ? '可在线体验' : '体验准备中' }}</span></div>
                <h3 :id="`${project.id}-heading`">{{ project.name }}</h3>
                <p class="project-description">{{ project.summary }}</p>
                <div class="project-tags" aria-label="项目技术"><span v-for="tag in project.tags" :key="tag">{{ tag }}</span></div>
                <div class="project-actions"><span class="detail-prompt">查看项目详情 <span aria-hidden="true">↗</span></span></div>
              </div>
            </article>
          </div>
          <p class="list-footnote">持续构建，也持续记录。更多作品会慢慢出现在这里。</p>
        </section>
        <aside id="playground" class="playground" aria-labelledby="playground-heading">
          <div class="section-title"><div><p class="eyebrow">PLAYGROUND</p><h2 id="playground-heading">小工具<span class="heading-dot">.</span></h2></div><span class="sidebar-spark" aria-hidden="true">✳</span></div>
          <DiceGame />
          <p class="sidebar-note">认真做点事，也记得放松一下。</p>
        </aside>
      </div>
    </main>
    <dialog ref="detailsDialog" class="project-dialog" aria-labelledby="detail-title" @close="restoreScroll" @click="closeOnBackdrop">
      <div class="detail-panel">
        <div class="detail-topbar"><span>PROJECT / 项目详情</span><button class="dialog-close" aria-label="关闭项目详情" autofocus @click="detailsDialog.close()">×</button></div>
        <img class="detail-image" :src="selectedProject.preview" :alt="selectedProject.previewAlt" width="1280" height="720" />
        <div class="detail-body">
          <p class="eyebrow">{{ selectedProject.category }}</p>
          <h2 id="detail-title">{{ selectedProject.name }}</h2>
          <div class="project-tags"><span v-for="tag in selectedProject.tags" :key="tag">{{ tag }}</span></div>
          <div class="detail-description"><p v-for="paragraph in selectedProject.description" :key="paragraph">{{ paragraph }}</p></div>
          <h3>可以做什么</h3>
          <ul class="detail-features"><li v-for="feature in selectedProject.features" :key="feature">{{ feature }}</li></ul>
          <div class="detail-links"><a v-if="tripAvailable" class="primary-action" :href="selectedProject.demoUrl" target="_blank" rel="noopener noreferrer">在线演示 ↗</a><button v-else class="primary-action" disabled>在线演示 · 准备中</button><a class="source-link" :href="selectedProject.sourceUrl" target="_blank" rel="noopener noreferrer">GitHub 源码 ↗</a></div>
          <p v-if="!tripAvailable" class="demo-note">在线演示暂未开放。</p>
        </div>
      </div>
    </dialog>
    <footer><a class="brand" href="#about">保持好奇<span class="dot">.</span></a><span>一步一步，把想法变成作品。</span><a href="#about">回到顶部 ↑</a></footer>
  </div>
</template>
