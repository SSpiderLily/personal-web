<script setup>
import { computed, onMounted, ref } from 'vue'
import ImageUpload from './ImageUpload.vue'
import ProjectContent from '../components/ProjectContent.vue'
import { editableProject, emptyProject, parseProject, projectImageUrl } from '../projects/projectContent.js'

const props = defineProps({ api: { type: Object, required: true } })
const emit = defineEmits(['unauthenticated'])
const projects = ref([])
const draft = ref(null)
const baseline = ref(null)
const selectedId = ref(null)
const selectedStatus = ref('draft')
const pendingSelection = ref(undefined)
const loading = ref(false)
const busy = ref(false)
const uploading = ref(0)
const blocked = computed(() => busy.value || loading.value || uploading.value > 0)
const uploadApi = { upload: async file => {
  uploading.value++
  try { return await props.api.upload(file) }
  finally { uploading.value-- }
} }
const ready = ref(false)
const preview = ref(false)
const error = ref('')
const notice = ref('')
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseline.value))
const lines = value => value.split('\n').filter(item => item.trim().length)
const techText = computed({ get: () => draft.value?.tech_stack.join('\n') || '', set: value => { draft.value.tech_stack = value.split('\n') } })
const featureText = computed({ get: () => draft.value?.features.join('\n') || '', set: value => { draft.value.features = value.split('\n') } })
const labels = { draft: '草稿', published: '已发布', archived: '已下架' }

function clear() {
  draft.value = null; baseline.value = null; selectedId.value = null; pendingSelection.value = undefined; projects.value = []; preview.value = false; ready.value = false
}
function failure(reason) {
  if (reason?.status === 401) { clear(); error.value = '登录已失效，请重新登录。'; emit('unauthenticated') }
  else if (reason?.status === 400) error.value = '项目内容不符合要求。发布项目需要名称、简介、技术栈、封面和有效详情。请检查长度、图片和链接。'
  else if (reason?.status === 404) error.value = '项目不存在，请重新加载列表。当前编辑仍保留。'
  else if (reason?.status === 409) error.value = '项目状态已改变，请重新读取后操作。当前编辑仍保留。'
  else if (reason?.status === 403) error.value = '安全验证失败，请刷新会话后重试。当前编辑仍保留。'
  else error.value = '项目服务暂时不可用，请稍后重试。当前编辑仍保留。'
}
function parseList(value) {
  if (!Array.isArray(value?.projects)) throw new Error('invalid project list')
  const items = value.projects.map(parseProject)
  if (new Set(items.map(item => item.id)).size !== items.length) throw new Error('duplicate project')
  return items
}
function accept(value) {
  const item = parseProject(value?.project)
  draft.value = editableProject(item); baseline.value = editableProject(item)
  selectedId.value = item.id; selectedStatus.value = item.status
  const index = projects.value.findIndex(project => project.id === item.id)
  if (index < 0) projects.value.push(item)
  else projects.value[index] = item
}
async function load() {
  if (blocked.value) return
  loading.value = true; error.value = ''
  try { projects.value = parseList(await props.api.list()); ready.value = true }
  catch (reason) { failure(reason) }
  finally { loading.value = false }
}
async function openProject(id) {
  if (blocked.value) return
  error.value = ''; notice.value = ''; preview.value = false
  if (id === null) { draft.value = emptyProject(); baseline.value = null; selectedId.value = null; selectedStatus.value = 'draft'; return }
  loading.value = true
  try { accept(await props.api.get(id)) }
  catch (reason) { failure(reason) }
  finally { loading.value = false }
}
async function selectProject(id) {
  if (blocked.value) return
  if (draft.value && dirty.value) { pendingSelection.value = id; return }
  await openProject(id)
}
async function confirmSelection() {
  const id = pendingSelection.value; pendingSelection.value = undefined
  if (id !== undefined) await openProject(id)
}
async function save() {
  if (!draft.value || blocked.value) return
  busy.value = true; error.value = ''; notice.value = ''
  const value = editableProject(draft.value)
  value.tech_stack = lines(value.tech_stack.join('\n')); value.features = lines(value.features.join('\n'))
  try {
    accept(selectedId.value === null ? await props.api.create(value) : await props.api.save(selectedId.value, value))
    notice.value = selectedStatus.value === 'published' ? '已保存并更新公开项目。' : '草稿已保存。'
  } catch (reason) { failure(reason) }
  finally { busy.value = false }
}
async function publish() {
  if (!draft.value || selectedId.value === null || dirty.value || blocked.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { accept(await props.api.publish(selectedId.value)); notice.value = '项目已发布。' }
  catch (reason) { failure(reason) }
  finally { busy.value = false }
}
async function archive() {
  if (selectedStatus.value !== 'published' || dirty.value || blocked.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { accept(await props.api.archive(selectedId.value)); notice.value = '项目已下架。' }
  catch (reason) { failure(reason) }
  finally { busy.value = false }
}
async function moveProject(id, offset) {
  if (blocked.value) return
  const ids = projects.value.map(item => item.id), from = ids.indexOf(id), to = from + offset
  if (from < 0 || to < 0 || to >= ids.length) return
  ;[ids[from], ids[to]] = [ids[to], ids[from]]
  busy.value = true; error.value = ''
  try { projects.value = parseList(await props.api.reorder(ids)); notice.value = '展示顺序已保存。' }
  catch (reason) { failure(reason) }
  finally { busy.value = false }
}
function moveItem(items, index, offset) {
  const target = index + offset
  if (blocked.value || target < 0 || target >= items.length) return
  ;[items[index], items[target]] = [items[target], items[index]]
}
function addText() { if (draft.value && draft.value.blocks.length < 100) draft.value.blocks.push({ kind: 'text', body: '' }) }
function addImage(image, target) {
  if (!draft.value || !projectImageUrl(image?.id)) return
  const items = draft.value[target]
  if (!items || items.length >= (target === 'blocks' ? 100 : 30)) return
  if (target === 'screenshots' && items.some(item => item.file_id === image.id)) { error.value = '同一项目截图不能重复。'; return }
  items.push({ ...(target === 'blocks' ? { kind: 'image' } : {}), file_id: image.id, caption: '' })
}
function setCover(image) { if (draft.value && projectImageUrl(image?.id)) draft.value.cover_file_id = image.id }
function reset() { if (!blocked.value) { draft.value = baseline.value ? editableProject(baseline.value) : emptyProject(); error.value = ''; notice.value = '' } }
defineExpose({ dirty, clear })
onMounted(load)
</script>

<template>
  <section class="projects-panel" aria-label="项目管理" :aria-busy="blocked">
    <p class="intro">先保存草稿，再预览和发布。已发布项目保存成功后立即更新公开内容。</p>
    <p v-if="loading" role="status">正在加载项目…</p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <div class="list-actions"><button :disabled="blocked" @click="selectProject(null)">新增项目</button><button :disabled="blocked" @click="load">重新加载列表</button></div>
    <p v-if="ready && !projects.length">暂无项目。新增并发布后会在首页展示。</p>
    <ul class="project-list">
      <li v-for="(item, index) in projects" :key="item.id">
        <button class="project-select" :aria-pressed="selectedId === item.id" :disabled="blocked" @click="selectProject(item.id)">{{ item.name || '未命名项目' }} · {{ labels[item.status] }}</button>
        <button :aria-label="`${item.name || '项目'} 上移`" :disabled="blocked || index === 0" @click="moveProject(item.id, -1)">上移</button>
        <button :aria-label="`${item.name || '项目'} 下移`" :disabled="blocked || index === projects.length - 1" @click="moveProject(item.id, 1)">下移</button>
      </li>
    </ul>
    <div v-if="pendingSelection !== undefined" role="alertdialog" aria-label="未保存更改" class="discard-prompt">
      <p>当前有未保存的更改。切换项目会丢弃这些更改。</p>
      <button @click="confirmSelection">丢弃并切换</button><button @click="pendingSelection = undefined">继续编辑</button>
    </div>
    <template v-if="draft">
      <div class="editor-heading"><h3>{{ selectedId ? '编辑项目' : '新建草稿' }} · {{ labels[selectedStatus] }}</h3><span v-if="dirty">有未保存的更改</span></div>
      <form @submit.prevent="save">
        <fieldset :disabled="blocked">
          <legend>基本信息</legend>
          <label>项目名称<input v-model="draft.name" maxlength="100"></label>
          <label>项目简介<textarea v-model="draft.summary" maxlength="2000" rows="3"></textarea></label>
          <label>分类<input v-model="draft.category" maxlength="100"></label>
          <label>技术栈（每行一项，最多20项）<textarea v-model="techText" rows="3"></textarea></label>
          <label>项目特点（每行一项，最多30项）<textarea v-model="featureText" rows="3"></textarea></label>
          <label>在线体验链接<input :value="draft.demo_url || ''" maxlength="2048" placeholder="https://… 或 /trip/" @input="draft.demo_url = $event.target.value || null"></label>
          <label>源码链接<input :value="draft.source_url || ''" maxlength="2048" placeholder="https://…" @input="draft.source_url = $event.target.value || null"></label>
        </fieldset>
        <fieldset :disabled="blocked"><legend>封面</legend>
          <img v-if="draft.cover_file_id" class="cover-preview" :src="projectImageUrl(draft.cover_file_id, true)" :alt="draft.cover_alt || '封面预览'">
          <ImageUpload :api="uploadApi" @update:model-value="setCover" @unauthenticated="failure({ status: 401 })" />
          <label>封面替代文字<input v-model="draft.cover_alt" maxlength="500"></label>
          <button v-if="draft.cover_file_id" type="button" @click="draft.cover_file_id = null">移除封面</button>
        </fieldset>
        <fieldset :disabled="blocked"><legend>图文详情（最多100块）</legend>
          <div v-for="(block, index) in draft.blocks" :key="index" class="content-item">
            <label v-if="block.kind === 'text'">文本块 {{ index + 1 }}<textarea v-model="block.body" maxlength="10000" rows="5"></textarea></label>
            <template v-else><img :src="projectImageUrl(block.file_id, true)" alt="详情图片预览"><label>图片说明<input v-model="block.caption" maxlength="500"></label>
              <ImageUpload :api="uploadApi" @update:model-value="block.file_id = $event.id" @unauthenticated="failure({ status: 401 })" />
            </template>
            <div class="item-actions"><button type="button" :disabled="index === 0" @click="moveItem(draft.blocks, index, -1)">上移</button><button type="button" :disabled="index === draft.blocks.length - 1" @click="moveItem(draft.blocks, index, 1)">下移</button><button type="button" @click="draft.blocks.splice(index, 1)">删除块</button></div>
          </div>
          <button type="button" :disabled="draft.blocks.length >= 100" @click="addText">添加文本块</button>
          <p>添加图片块：</p><ImageUpload v-if="draft.blocks.length < 100" :api="uploadApi" @update:model-value="addImage($event, 'blocks')" @unauthenticated="failure({ status: 401 })" />
        </fieldset>
        <fieldset :disabled="blocked"><legend>项目截图（最多30张）</legend>
          <div v-for="(shot, index) in draft.screenshots" :key="shot.file_id" class="content-item">
            <img :src="projectImageUrl(shot.file_id, true)" alt="截图预览"><label>截图说明<input v-model="shot.caption" maxlength="500"></label>
            <div class="item-actions"><button type="button" :disabled="index === 0" @click="moveItem(draft.screenshots, index, -1)">上移</button><button type="button" :disabled="index === draft.screenshots.length - 1" @click="moveItem(draft.screenshots, index, 1)">下移</button><button type="button" @click="draft.screenshots.splice(index, 1)">删除截图</button></div>
          </div>
          <ImageUpload v-if="draft.screenshots.length < 30" :api="uploadApi" @update:model-value="addImage($event, 'screenshots')" @unauthenticated="failure({ status: 401 })" />
        </fieldset>
        <div class="editor-actions">
          <button type="submit" :disabled="blocked || !dirty">{{ busy ? '正在处理…' : selectedStatus === 'published' ? '保存并更新' : '保存草稿' }}</button>
          <button type="button" :disabled="blocked" @click="preview = !preview">{{ preview ? '收起预览' : '预览当前编辑' }}</button>
          <button type="button" :disabled="blocked || !dirty" @click="reset">撤销编辑</button>
          <button v-if="selectedStatus !== 'published'" type="button" :disabled="blocked || dirty || selectedId === null" @click="publish">发布项目</button>
          <button v-else type="button" :disabled="blocked || dirty" @click="archive">下架项目</button>
        </div>
        <p v-if="dirty" class="hint">发布或下架前请先保存编辑。预览只展示当前编辑，不会保存。</p>
      </form>
      <section v-if="preview" class="preview" aria-label="项目草稿预览"><ProjectContent :project="draft" private-images /></section>
    </template>
  </section>
</template>

<style scoped>
.projects-panel { color: var(--admin-ink, #304130); font-size: 13px; }
.intro, .hint { color: #73806a; line-height: 1.8; }
button { min-height: 44px; padding: 8px 12px; border: 1px solid #dce2d3; border-radius: 7px; background: #f6f7f1; color: #3d6041; font: inherit; cursor: pointer; }
button:disabled { opacity: .45; cursor: default; }
.project-list { list-style: none; padding: 0; }
.project-list li, .list-actions, .item-actions, .editor-actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.project-select { flex: 1; text-align: left; min-width: 140px; }
.project-select[aria-pressed="true"] { border-color: #3d6041; background: #eaf0e3; }
fieldset { min-width: 0; padding: 18px; margin: 18px 0; border: 1px solid #dce2d3; border-radius: 12px; background: #fffefa; }
legend { padding: 0 8px; font-weight: 600; }
label { display: grid; gap: 8px; margin: 14px 0; line-height: 1.6; }
input, textarea { min-width: 0; width: 100%; box-sizing: border-box; border: 1px solid #ccd5c3; border-radius: 6px; padding: 10px; color: inherit; background: white; font: inherit; }
textarea { resize: vertical; }
.content-item { padding: 14px 0; border-bottom: 1px solid #e6ebdf; }
.cover-preview, .content-item img { display: block; max-width: 100%; max-height: 240px; object-fit: contain; }
.error { color: #a33e35; line-height: 1.8; }
.preview, .discard-prompt { padding: 20px; margin: 20px 0; border: 1px solid #ccd5c3; border-radius: 12px; background: #fff; }
.discard-prompt button + button { margin-left: 8px; }
.editor-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
@media(max-width:540px) { fieldset, .preview { padding: 12px; } .editor-actions button { flex: 1 1 40%; } }
</style>
