<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import ImageUpload from './ImageUpload.vue'

const props = defineProps({ api: { type: Object, required: true } })
const emit = defineEmits(['unauthenticated', 'dirty-change'])
const empty = () => ({ name: '', title: '', introduction: '', skills: [], avatar_file_id: null, contacts: [], social_links: [] })
const clone = value => JSON.parse(JSON.stringify(value))
const draft = ref(empty())
const baseline = ref(empty())
const skillsText = ref('')
const aboutFields = [
  ['page_title','页面标题',200],['page_intro','页面开场白',1000],['about_heading','介绍标题',200],
  ['about_body','详细介绍',10000],['current_heading','近期项目板块标题',200],['current_project_label','近期项目名称',200],
  ['current_project_url','近期项目链接',1000],['contact_heading','联系板块标题',200],['contact_intro','联系方式说明',2000],
]
const uploadedAvatar = ref(null)
const uploading = ref(false)
const uploadApi = { async upload(file) { uploading.value = true; try { return await props.api.upload(file) } finally { uploading.value = false } } }
const loading = ref(false), saving = ref(false), ready = ref(false), error = ref(''), saved = ref(false)
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseline.value) || skillsText.value !== baseline.value.skills.join('\n'))
const avatar = computed(() => draft.value.avatar_file_id ? { id: draft.value.avatar_file_id, url: `/api/admin/files/${draft.value.avatar_file_id}` } : null)
function normalized(value) {
  const result = empty()
  for (const key of ['name', 'title', 'introduction']) {
    if (typeof value?.[key] !== 'string') throw new Error('invalid response')
    result[key] = value[key]
  }
  if (!Array.isArray(value.skills) || value.skills.some(item => typeof item !== 'string') ||
      (value.avatar_file_id !== null && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.avatar_file_id))) throw new Error('invalid response')
  result.skills = [...value.skills]
  result.avatar_file_id = value.avatar_file_id
  for (const key of ['contacts', 'social_links']) {
    if (!Array.isArray(value[key]) || value[key].some(item => typeof item?.label !== 'string' || typeof item?.url !== 'string')) throw new Error('invalid response')
    result[key] = value[key].map(item => ({ label: item.label, url: item.url }))
  }
  if(value.about_content) {
    if(typeof value.about_content!=='object' || Array.isArray(value.about_content)) throw new Error('invalid response')
    result.about_content={...value.about_content}
  }
  return result
}
function clearDraft() { draft.value = empty(); baseline.value = empty(); skillsText.value = ''; uploadedAvatar.value = null; ready.value = false; saved.value = false }
function failure(reason) {
  if (reason?.status === 401) { clearDraft(); error.value = '登录已失效，请重新登录。'; emit('unauthenticated') }
  else if (reason?.status === 400) error.value = '资料格式不正确，请检查长度、链接和头像后重试。'
  else if (reason?.status === 403) error.value = '安全验证失败，请刷新页面后重试。'
  else error.value = '资料暂时不可用，请稍后重试。'
}
function accept(value) { const item = normalized(value); draft.value = clone(item); baseline.value = clone(item); skillsText.value = item.skills.join('\n'); uploadedAvatar.value = null; ready.value = true }
async function load() {
  if (loading.value || saving.value || uploading.value) return
  loading.value = true; error.value = ''
  try { const value = await props.api.load(); if (!dirty.value) accept(value) }
  catch (reason) { failure(reason) }
  finally { loading.value = false }
}
async function save() {
  if (!ready.value || loading.value || saving.value || uploading.value || !dirty.value) return
  saving.value = true; error.value = ''; saved.value = false
  try {
    const payload = clone(draft.value)
    payload.skills = skillsText.value.split('\n').map(item => item.trim()).filter(Boolean)
    accept(await props.api.save(payload)); saved.value = true
  }
  catch (reason) { failure(reason) }
  finally { saving.value = false }
}
function reset() { if (!saving.value) { draft.value = clone(baseline.value); skillsText.value = baseline.value.skills.join('\n'); uploadedAvatar.value = null; error.value = ''; saved.value = false } }
function setAbout(key,value) { draft.value.about_content={...(draft.value.about_content || {}),[key]:value} }
function setAvatar(value) {
  if (!ready.value) return
  if (!value) { draft.value.avatar_file_id = null; uploadedAvatar.value = null; return }
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.id || '')) { failure({ status: 400 }); return }
  draft.value.avatar_file_id = value.id
  uploadedAvatar.value = ['width', 'height', 'byte_size'].every(key => Number.isFinite(value[key]) && value[key] > 0)
    ? { ...value, url: `/api/admin/files/${value.id}` } : null
}
function guardLeave(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
function revalidate() { if (ready.value) return load() }
watch(dirty, value => { if (value) saved.value = false; emit('dirty-change', value) })
onMounted(() => { load(); if (typeof window !== 'undefined') { window.addEventListener('beforeunload', guardLeave); window.addEventListener('focus', revalidate) } })
onBeforeUnmount(() => { clearDraft(); if (typeof window !== 'undefined') { window.removeEventListener('beforeunload', guardLeave); window.removeEventListener('focus', revalidate) } })
defineExpose({ dirty, clearDraft, revalidate })
</script>

<template>
  <section class="profile-panel" aria-label="个人资料编辑" :aria-busy="loading || saving">
    <p>填写公开显示的个人资料。所有字段均可留空。</p>
    <p v-if="loading" role="status">正在加载资料…</p>
    <div v-if="error" role="alert"><p>{{ error }}</p><button v-if="!ready" :disabled="loading" @click="load">重试加载</button></div>
    <form v-if="ready" @submit.prevent="save">
      <fieldset :disabled="loading || saving">
        <legend>基本资料</legend>
        <label>姓名<input v-model="draft.name" aria-label="姓名" maxlength="100"></label>
        <label>头衔<input v-model="draft.title" aria-label="头衔" maxlength="200"></label>
        <label>介绍<textarea v-model="draft.introduction" aria-label="介绍" maxlength="20000" rows="7"></textarea></label>
        <label>技能（每行一项，最多30项）<textarea v-model="skillsText" aria-label="技能" rows="4"></textarea></label>
        <h3>头像</h3>
        <img v-if="avatar && !uploadedAvatar" class="profile-avatar" :src="avatar.url" alt="当前头像预览">
        <ImageUpload :api="uploadApi" :model-value="uploadedAvatar" @update:model-value="setAvatar" @unauthenticated="failure({ status: 401 })" />
        <button v-if="draft.avatar_file_id" type="button" @click="setAvatar(null)">移除头像</button>
      </fieldset>
      <fieldset v-for="group in [{ key: 'contacts', label: '联系方式' }, { key: 'social_links', label: '社交链接' }]" :key="group.key" :disabled="loading || saving">
        <legend>{{ group.label }}</legend>
        <p>{{ group.key === 'contacts' ? '支持 HTTP(S)、mailto:邮箱和 tel:电话号码。' : '仅支持完整 HTTP(S) 地址。' }}</p>
        <div v-for="(link, index) in draft[group.key]" :key="index" class="profile-link">
          <label>名称<input v-model="link.label" :aria-label="`${group.label} ${index + 1} 名称`" maxlength="100" required></label>
          <label>链接<input v-model="link.url" :aria-label="`${group.label} ${index + 1} 链接`" maxlength="2048" required></label>
          <button type="button" @click="draft[group.key].splice(index, 1)">移除 {{ group.label }} {{ index + 1 }}</button>
        </div>
        <button type="button" :disabled="draft[group.key].length >= 20" @click="draft[group.key].push({ label: '', url: '' })">添加{{ group.label }}</button>
      </fieldset>
      <fieldset :disabled="loading || saving || uploading"><legend>关于页面文案</legend><p>留空字段使用默认文案。项目入口使用 /#/works 或完整 HTTP(S) 链接。</p><label v-for="[key,label,limit] in aboutFields" :key="key">{{ label }}<textarea v-if="key==='about_body' || key==='contact_intro'" :value="draft.about_content?.[key] || ''" :aria-label="label" :maxlength="limit" rows="5" @input="setAbout(key,$event.target.value)"></textarea><input v-else :value="draft.about_content?.[key] || ''" :aria-label="label" :maxlength="limit" @input="setAbout(key,$event.target.value)"></label></fieldset>
      <div class="profile-actions"><button type="submit" :disabled="loading || saving || uploading || !dirty" @click.prevent="save">{{ saving ? '正在保存…' : '保存资料' }}</button><button type="button" :disabled="loading || saving || uploading || !dirty" @click="reset">撤销更改</button><span v-if="saved" role="status">已保存</span><span v-else-if="dirty">有未保存的更改</span></div>
    </form>
  </section>
</template>

<style scoped>
.profile-panel { color: var(--admin-ink, #304130); font-size: 13px; }
fieldset { min-width: 0; margin: 20px 0; padding: 20px; border: 1px solid #dce2d3; border-radius: 12px; background: #fffefa; }
legend { font-weight: 600; padding: 0 8px; }
label { display: grid; gap: 8px; margin-bottom: 16px; }
input, textarea { box-sizing: border-box; width: 100%; padding: 10px; border: 1px solid #dce2d3; border-radius: 6px; font: inherit; background: white; color: inherit; }
textarea { resize: vertical; }
.profile-avatar { display: block; max-width: 100%; max-height: 20rem; margin-bottom: 12px; border-radius: 8px; object-fit: contain; }
button { min-height: 44px; padding: 8px 14px; border: 1px solid #dce2d3; border-radius: 6px; background: #f6f7f1; color: #3d6041; font: inherit; cursor: pointer; }
button:disabled { opacity: .5; cursor: default; }
.profile-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.profile-actions button:first-child { background: #3d6041; color: white; }
.profile-link { border-bottom: 1px solid #dce2d3; padding: 12px 0; margin-bottom: 12px; }
[role=alert] { color: #a33e35; }
@media(max-width:540px) { fieldset { padding: 12px; } }
</style>
