<script setup>
import { computed } from 'vue'
const props = defineProps({ profile: { type: Object, required: true } })
const avatarUrl = computed(() => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(props.profile.avatar_file_id || '') ? `/api/files/${props.profile.avatar_file_id}` : '')
function safeLinks(items, contacts) {
  return (Array.isArray(items) ? items : []).filter(item => {
    if (typeof item?.label !== 'string' || typeof item?.url !== 'string' || /[\s\\\u0000-\u001f\u007f]/.test(item.url)) return false
    try {
      if (/[\u0000-\u0020\u007f\\]/.test(decodeURIComponent(item.url))) return false
      const url = new URL(item.url)
      if (['http:', 'https:'].includes(url.protocol)) return !!url.hostname && !url.username && !url.password
      if (!contacts) return false
      if (url.protocol === 'mailto:') return /^mailto:[A-Za-z0-9.!#$&'*+/=_`{|}~-]+@[A-Za-z0-9][A-Za-z0-9.-]*$/i.test(item.url)
      return /^tel:\+?[0-9][0-9().-]*$/i.test(item.url)
    } catch { return false }
  })
}
const contacts = computed(() => safeLinks(props.profile.contacts, true))
const social = computed(() => safeLinks(props.profile.social_links, false))
</script>

<template>
  <section class="public-profile" aria-label="个人资料">
    <img v-if="avatarUrl" class="public-profile__avatar" :src="avatarUrl" :alt="profile.name ? `${profile.name}的头像` : '头像'">
    <h1 v-if="profile.name">{{ profile.name }}</h1>
    <p v-if="profile.title" class="public-profile__title">{{ profile.title }}</p>
    <p v-if="profile.introduction" class="public-profile__introduction">{{ profile.introduction }}</p>
    <ul v-if="profile.skills?.length" class="public-profile__skills" aria-label="技能"><li v-for="(skill, index) in profile.skills" :key="index">{{ skill }}</li></ul>
    <nav v-if="contacts.length || social.length" aria-label="联系与社交链接"><a v-for="(link,index) in [...contacts, ...social]" :key="index" :href="link.url" rel="noopener noreferrer">{{ link.label }}</a></nav>
  </section>
</template>

<style scoped>
.public-profile__avatar { width: 96px; height: 96px; object-fit: cover; border-radius: 50%; }
.public-profile__title { color: var(--color-muted, #687282); }
.public-profile__introduction { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.9; }
.public-profile__skills { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; }
.public-profile__skills li { padding: 5px 10px; background: #f0f3ec; border-radius: 20px; }
nav { display: flex; flex-wrap: wrap; gap: 16px; }
</style>
