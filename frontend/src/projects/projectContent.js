const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i
export function projectImageUrl(id, privateImages = false) {
  return typeof id === 'string' && uuid.test(id) ? `/api/${privateImages ? 'admin/' : ''}files/${id}` : null
}
export function projectLink(value, env = import.meta.env || {}) {
  if (value === '/trip/') {
    const configured = env.VITE_TRIP_DEMO_URL
    if (configured) return configured === '/trip/' ? '/trip/' : projectLink(configured, {})
    return env.DEV ? 'http://127.0.0.1:5173/' : '/trip/'
  }
  if (typeof value !== 'string' || value.length > 2048 || /[\x00-\x20\x7f-\x9f\\]/.test(value)) return null
  try {
    if (/[\x00-\x20\x7f-\x9f\\]/.test(decodeURIComponent(value))) return null
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? value : null
  } catch { return null }
}
export function emptyProject() {
  return { name: '', summary: '', category: '', tech_stack: [], features: [], cover_file_id: null,
    cover_alt: '', demo_url: null, source_url: null, blocks: [], screenshots: [] }
}
export function editableProject(value) {
  const result = {}
  for (const key of Object.keys(emptyProject())) result[key] = JSON.parse(JSON.stringify(value[key]))
  return result
}
export function parseProject(value) {
  const text = (value, max) => typeof value === 'string' && value.length <= max && !/[\u0000\ud800-\udfff]/u.test(value)
  const strings = (value, max, length) => Array.isArray(value) && value.length <= max && value.every(item => text(item, length) && item.length > 0)
  if (!value || !Number.isSafeInteger(value.id) || value.id < 1 || !['draft', 'published', 'archived'].includes(value.status) ||
      !Number.isInteger(value.sort_order) || value.sort_order < 0 || !text(value.name, 100) || !text(value.summary, 2000) ||
      !text(value.category, 100) || !text(value.cover_alt, 500) || !strings(value.tech_stack, 20, 100) || !strings(value.features, 30, 500) ||
      (value.cover_file_id !== null && !projectImageUrl(value.cover_file_id)) ||
      (value.demo_url !== null && !projectLink(value.demo_url, {})) || (value.source_url !== null && (!projectLink(value.source_url, {}) || value.source_url === '/trip/')) ||
      !Array.isArray(value.blocks) || value.blocks.length > 100 || !value.blocks.every(block => block?.kind === 'text'
        ? text(block.body, 10000) : block?.kind === 'image' && projectImageUrl(block.file_id) && text(block.caption, 500)) ||
      !Array.isArray(value.screenshots) || value.screenshots.length > 30 || !value.screenshots.every(image => projectImageUrl(image?.file_id) && text(image.caption, 500)) ||
      new Set(value.screenshots.map(image => image.file_id.toLowerCase())).size !== value.screenshots.length ||
      typeof value.updated_at !== 'string' || !Number.isFinite(Date.parse(value.updated_at)) ||
      (value.published_at !== null && (typeof value.published_at !== 'string' || !Number.isFinite(Date.parse(value.published_at))))) throw new Error('invalid project response')
  return { ...editableProject(value), id: value.id, status: value.status, sort_order: value.sort_order, published_at: value.published_at, updated_at: value.updated_at }
}
