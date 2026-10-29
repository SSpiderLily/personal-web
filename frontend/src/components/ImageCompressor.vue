<script setup>
import { ref, shallowRef, computed, watch, onBeforeUnmount } from 'vue'
import { validateImageFile, imageSize, compressImage, outputName, formatBytes } from '../tools/imageProcessing.js'

const file = shallowRef(null), bitmap = shallowRef(null), result = shallowRef(null)
const originalUrl = ref(''), resultUrl = ref('')
const type = ref('image/webp'), quality = ref(80), maxEdge = ref(1920)
const reading = ref(false), processing = ref(false), error = ref(''), dragging = ref(false)
let alive = true, readVersion = 0, processVersion = 0
const size = computed(() => {
  if (!bitmap.value) return null
  try { return imageSize(bitmap.value.width, bitmap.value.height, Number(maxEdge.value)) } catch { return null }
})
const reduction = computed(() => result.value ? Math.round((1 - result.value.blob.size / file.value.size) * 100) : 0)
function clearResult() {
  processVersion++
  processing.value = false
  if (resultUrl.value) URL.revokeObjectURL(resultUrl.value)
  resultUrl.value = ''
  result.value = null
}
watch([type, quality, maxEdge], clearResult)
async function selectFile(candidate) {
  if (!candidate) return
  const version = ++readVersion
  clearResult()
  error.value = ''
  reading.value = true
  try {
    validateImageFile(candidate)
    const decoded = await createImageBitmap(candidate)
    if (!alive || version !== readVersion) { decoded.close(); return }
    try { imageSize(decoded.width, decoded.height, 4096) } catch (reason) { decoded.close(); throw reason }
    bitmap.value?.close()
    if (originalUrl.value) URL.revokeObjectURL(originalUrl.value)
    bitmap.value = decoded
    file.value = candidate
    originalUrl.value = URL.createObjectURL(candidate)
  } catch (reason) {
    if (alive && version === readVersion) error.value = reason instanceof Error && reason.message.includes('。') ? reason.message : '无法读取这张图片，请选择有效的 JPEG、PNG 或 WebP 文件。'
  } finally { if (alive && version === readVersion) reading.value = false }
}
function pick(event) { void selectFile(event.target.files?.[0]); event.target.value = '' }
function drop(event) { dragging.value = false; void selectFile(event.dataTransfer.files?.[0]) }
async function process() {
  if (!bitmap.value || reading.value || processing.value || !size.value) return
  clearResult()
  const version = processVersion
  processing.value = true
  error.value = ''
  const settings = { type: type.value, quality: Number(quality.value) / 100, maxEdge: Number(maxEdge.value) }
  const name = file.value.name
  try {
    const value = await compressImage(bitmap.value, settings)
    if (!alive || version !== processVersion) return
    result.value = { ...value, name: outputName(name, settings.type) }
    resultUrl.value = URL.createObjectURL(value.blob)
  } catch (reason) { if (alive && version === processVersion) error.value = reason.message || '图片处理失败，请重试。' }
  finally { if (alive && version === processVersion) processing.value = false }
}
onBeforeUnmount(() => {
  alive = false; readVersion++; processVersion++
  bitmap.value?.close()
  if (originalUrl.value) URL.revokeObjectURL(originalUrl.value)
  if (resultUrl.value) URL.revokeObjectURL(resultUrl.value)
})
</script>

<template>
  <section class="local-tool compressor" aria-label="本站图片压缩">
    <label class="image-drop" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="drop">
      <span class="drop-symbol" aria-hidden="true">↥</span>
      <strong>{{ reading ? '正在读取图片…' : file ? '更换图片，或拖入另一张' : '选择图片，或拖到这里' }}</strong>
      <span>JPEG / PNG / WebP · 最多 20 MB、2000 万像素 · 动图仅保留单帧</span>
      <input type="file" accept="image/jpeg,image/png,image/webp" aria-label="选择图片" @change="pick">
    </label>
    <fieldset class="image-settings" :disabled="!bitmap || reading">
      <legend class="sr-only">图片输出设置</legend>
      <label>输出格式<select v-model="type"><option value="image/webp">WebP</option><option value="image/jpeg">JPEG</option><option value="image/png">PNG</option></select></label>
      <label>最长边（像素）<input v-model="maxEdge" type="number" min="1" max="4096" step="1" inputmode="numeric"></label>
      <label class="quality-control">{{ type === 'image/png' ? 'PNG 无损编码，不调整质量' : `图片质量 · ${quality}%` }}<input v-model="quality" type="range" min="10" max="100" :disabled="type === 'image/png'" aria-label="图片质量"></label>
      <button class="local-primary" type="button" :disabled="!size || processing || reading" @click="process">{{ processing ? '正在处理…' : '处理图片' }}</button>
    </fieldset>
    <p class="local-hint">{{ type === 'image/jpeg' ? 'JPEG 的透明区域会填成白色。' : 'WebP 和 PNG 保留透明区域。' }}不会放大原图；压缩后不一定更小，可调整格式、尺寸或质量。</p>
    <p v-if="bitmap && !size" class="local-error" role="alert">请输入 1–4096 之间的最长边尺寸。</p>
    <p v-if="error" class="local-error" role="alert">{{ error }}</p>
    <div v-if="file" class="image-comparison">
      <figure><figcaption><strong>原图</strong><span>{{ formatBytes(file.size) }} · {{ bitmap.width }} × {{ bitmap.height }}</span></figcaption><div class="image-preview"><img :src="originalUrl" alt="待处理原图"></div><p class="image-name">{{ file.name }}</p></figure>
      <figure><figcaption><strong>处理结果</strong><span v-if="result">{{ formatBytes(result.blob.size) }} · {{ result.width }} × {{ result.height }}</span><span v-else>等待处理</span></figcaption><div class="image-preview"><img v-if="result" :src="resultUrl" alt="处理后的图片"><p v-else>{{ processing ? '正在生成图片…' : '调整上方设置，点击「处理图片」。' }}</p></div><div v-if="result" class="image-result" role="status"><span>{{ reduction > 0 ? `体积减少 ${reduction}%` : '体积没有减小，可尝试降低质量或尺寸。' }}</span><a class="local-primary" :href="resultUrl" :download="result.name">下载图片 ↓</a></div></figure>
    </div>
    <p v-else class="local-empty">让图片轻一点，也让分享快一点。</p>
  </section>
</template>
