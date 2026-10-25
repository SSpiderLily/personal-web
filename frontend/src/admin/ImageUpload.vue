<script setup>
import { ref } from 'vue'

const props = defineProps({
  api: { type: Object, required: true },
  modelValue: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'unauthenticated'])
const busy = ref(false)
const error = ref('')
const messages = {
  file_too_large: '图片不能超过 10 MiB。',
  unsupported_image: '请选择静态 PNG、JPEG 或 WebP 图片，并确认文件扩展名正确。',
  invalid_image: '图片损坏或尺寸超过限制，请重新选择。',
  invalid_request: '上传请求不完整，请重新选择图片。',
  upload_unavailable: '图片服务暂时不可用，请稍后重试。',
  csrf_failed: '安全验证失败，请刷新后重试。',
  origin_forbidden: '当前来源不能上传图片。',
}

async function selectFile(event) {
  const input = event.target
  const file = input.files?.[0]
  if (busy.value || !file) return
  error.value = ''
  if (file.size < 1 || file.size > 10485760 || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    error.value = '请选择 1 字节至 10 MiB 的静态 PNG、JPEG 或 WebP 图片。'
    input.value = ''
    return
  }
  busy.value = true
  try {
    const value = await props.api.upload(file)
    emit('update:modelValue', value)
  } catch (failure) {
    if (failure?.status === 401) {
      error.value = '登录已失效，请重新登录。'
      emit('unauthenticated')
    } else {
      error.value = messages[failure?.code] || '图片上传失败，请稍后重试。'
    }
  } finally {
    input.value = ''
    busy.value = false
  }
}
</script>

<template>
  <section class="image-upload" :aria-busy="busy">
    <label class="image-upload__label">
      <span>{{ busy ? '正在上传…' : '选择图片' }}</span>
      <input type="file" accept="image/png,image/jpeg,image/webp" :disabled="busy" @change="selectFile">
    </label>
    <p class="image-upload__hint">静态 PNG、JPEG 或 WebP，最大 10 MiB、4000 万像素。</p>
    <p v-if="error" role="alert" class="image-upload__error">{{ error }}</p>
    <figure v-if="modelValue" class="image-upload__preview">
      <img :src="modelValue.url" alt="已上传图片预览">
      <figcaption>{{ modelValue.width }} × {{ modelValue.height }} · {{ modelValue.byte_size }} 字节</figcaption>
    </figure>
    <p v-else class="image-upload__hint">尚未选择图片。</p>
  </section>
</template>

<style scoped>
.image-upload { display: grid; gap: .65rem; min-width: 0; }
.image-upload__label { display: grid; gap: .5rem; font-weight: 600; }
.image-upload input { max-width: 100%; font: inherit; }
.image-upload__hint, .image-upload figcaption { margin: 0; color: #687282; font-size: .875rem; }
.image-upload__error { margin: 0; color: #a32d2d; }
.image-upload__preview { margin: 0; display: grid; gap: .4rem; }
.image-upload__preview img { display: block; max-width: 100%; max-height: 20rem; object-fit: contain; border-radius: .5rem; }
</style>
