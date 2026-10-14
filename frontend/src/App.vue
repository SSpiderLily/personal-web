<script setup>
import { onMounted, ref } from 'vue'
import DiceGame from './components/DiceGame.vue'
const profile = ref(null)
const loading = ref(true)
const error = ref('')
async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/profile', { signal: AbortSignal.timeout(8000) })
    if (!response.ok) throw new Error('Request failed')
    profile.value = await response.json()
  } catch {
    error.value = '暂时无法加载个人信息，请确认后端已启动后重试。'
  } finally {
    loading.value = false
  }
}
onMounted(loadProfile)
</script>

<template>
  <div class="page">
    <header><a class="brand" href="#">我的个人网站<span class="dot">.</span></a><a href="#about">关于我 ↗</a></header>
    <main>
      <p v-if="loading" role="status" class="notice">正在加载个人信息…</p>
      <div v-else-if="error" role="alert" class="notice"><p>{{ error }}</p><button @click="loadProfile">重新加载</button></div>
      <template v-else-if="profile">
        <section id="about" class="hero">
          <p class="eyebrow">HELLO, WORLD / 你好，世界</p>
          <p class="name">我是 {{ profile.name }}</p>
          <h1>{{ profile.title }}</h1>
          <p class="intro">{{ profile.introduction }}</p>
          <div class="tags"><span v-for="skill in profile.skills" :key="skill">{{ skill }}</span></div>
        </section>
        <section class="projects"><div class="section-title"><h2>正在做的事</h2><span>01 / 项目</span></div>
          <article v-for="project in profile.projects" :key="project.name"><span class="project-mark">↗</span><div><h3>{{ project.name }}</h3><p>{{ project.description }}</p></div><span class="badge">持续构建中</span></article>
        </section>
      </template>
      <DiceGame />
    </main>
    <footer><span>一步一步，把想法变成作品。</span><span>初版 · 默认展示内容</span></footer>
  </div>
</template>
