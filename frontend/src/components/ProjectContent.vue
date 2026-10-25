<script setup>
import { computed } from 'vue'
import { projectImageUrl, projectLink } from '../projects/projectContent.js'
const props = defineProps({ project: { type: Object, required: true }, privateImages: { type: Boolean, default: false } })
const demo = computed(() => projectLink(props.project.demo_url))
const source = computed(() => props.project.source_url === '/trip/' ? null : projectLink(props.project.source_url))
const imageUrl = id => projectImageUrl(id, props.privateImages)
</script>

<template>
  <article class="project-content">
    <p v-if="project.category" class="project-content__category">{{ project.category }}</p>
    <h2>{{ project.name || '未命名项目' }}</h2>
    <p v-if="project.summary" class="project-content__summary">{{ project.summary }}</p>
    <ul v-if="project.tech_stack?.length" class="project-content__tags" aria-label="技术栈">
      <li v-for="(item, index) in project.tech_stack" :key="index">{{ item }}</li>
    </ul>
    <img v-if="imageUrl(project.cover_file_id)" class="project-content__cover" :src="imageUrl(project.cover_file_id)" :alt="project.cover_alt || ''">
    <ul v-if="project.features?.length" class="project-content__features" aria-label="项目特点">
      <li v-for="(item, index) in project.features" :key="index">{{ item }}</li>
    </ul>
    <section v-if="project.blocks?.length" class="project-content__blocks" aria-label="项目详情">
      <template v-for="(block, index) in project.blocks" :key="index">
        <p v-if="block.kind === 'text'" class="project-content__text">{{ block.body }}</p>
        <figure v-else-if="block.kind === 'image' && imageUrl(block.file_id)">
          <img :src="imageUrl(block.file_id)" :alt="block.caption || ''" loading="lazy">
          <figcaption v-if="block.caption">{{ block.caption }}</figcaption>
        </figure>
      </template>
    </section>
    <section v-if="project.screenshots?.length" class="project-content__screenshots" aria-label="项目截图">
      <figure v-for="(shot, index) in project.screenshots" :key="index">
        <img v-if="imageUrl(shot.file_id)" :src="imageUrl(shot.file_id)" :alt="shot.caption || ''" loading="lazy">
        <figcaption v-if="shot.caption">{{ shot.caption }}</figcaption>
      </figure>
    </section>
    <nav v-if="demo || source" class="project-content__links" aria-label="项目链接">
      <a v-if="demo" :href="demo" target="_blank" rel="noopener noreferrer">在线体验</a>
      <a v-if="source" :href="source" target="_blank" rel="noopener noreferrer">查看源码</a>
    </nav>
  </article>
</template>

<style scoped>
.project-content { color: inherit; line-height: 1.8; overflow-wrap: anywhere; }
h2 { margin: 0 0 12px; font-size: clamp(1.4rem, 4vw, 2rem); line-height: 1.35; }
.project-content__category { margin: 0 0 6px; color: #6d7e61; font-size: .8rem; }
.project-content__summary, .project-content__text { white-space: pre-wrap; }
.project-content__summary { margin: 0 0 20px; color: #64705f; }
.project-content__tags { display: flex; flex-wrap: wrap; gap: 8px; padding: 0; list-style: none; }
.project-content__tags li { background: #edf1e7; padding: 3px 10px; border-radius: 999px; font-size: .8rem; }
img { display: block; width: 100%; max-height: 640px; object-fit: contain; border-radius: 10px; }
figure { margin: 24px 0; }
figcaption { margin-top: 8px; color: #718068; font-size: .85rem; }
.project-content__cover { margin: 24px 0; }
.project-content__features { padding-left: 20px; }
.project-content__links { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
.project-content__links a { padding: 10px 18px; border: 1px solid #cbd5bf; border-radius: 8px; color: #38563c; text-decoration: none; }
</style>
