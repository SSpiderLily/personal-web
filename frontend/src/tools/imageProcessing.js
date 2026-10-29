const formats = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' }

export function validateImageFile(file) {
  if (!file || !formats[file.type]) throw new Error('请选择 JPEG、PNG 或 WebP 图片。')
  if (file.size <= 0 || file.size > 20 * 1024 * 1024) throw new Error('图片不能为空，文件大小不能超过 20 MB。')
}

export function imageSize(width, height, maxEdge) {
  if (![width, height, maxEdge].every(n => Number.isFinite(n) && n > 0) || !Number.isInteger(maxEdge) || maxEdge > 4096) throw new Error('尺寸无效，最长边应为 1–4096 像素。')
  if (width * height > 20_000_000) throw new Error('图片超过 2000 万像素，请先缩小后重试。')
  const scale = Math.min(1, maxEdge / Math.max(width, height))
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) }
}

export function outputName(name, type) {
  if (!formats[type]) throw new Error('不支持的输出格式。')
  return `${name.replace(/\.[^.]+$/, '') || 'image'}-compressed.${formats[type]}`
}

export function formatBytes(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(2)} MB` : `${(bytes / 1024).toFixed(1)} KB`
}

export function encodeCanvas(canvas, type, quality = 0.8) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (!blob) reject(new Error('图片生成失败，请缩小尺寸后重试。'))
      else if (blob.type !== type) reject(new Error('当前浏览器不支持此输出格式，请选择 JPEG 或 PNG。'))
      else resolve(blob)
    }, type, quality)
  })
}

export async function compressImage(bitmap, { type, quality, maxEdge }) {
  const size = imageSize(bitmap.width, bitmap.height, maxEdge)
  const canvas = document.createElement('canvas')
  canvas.width = size.width
  canvas.height = size.height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('当前浏览器无法处理图片。')
  // JPEG cannot represent transparency. Use white rather than a black background.
  if (type === 'image/jpeg') { context.fillStyle = '#ffffff'; context.fillRect(0, 0, canvas.width, canvas.height) }
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  return { blob: await encodeCanvas(canvas, type, quality), ...size }
}
