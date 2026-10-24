import { parseToolSettings } from '../tools/publicTools.js'
const messages = {
  project_not_found: '项目不存在或已下架。',
  project_conflict: '项目状态已变化，请刷新后重试。',
  invalid_credentials: '账号或密码不正确，请重试。',
  unauthenticated: '登录已失效，请重新登录。',
  csrf_failed: '会话验证失败，请刷新页面后重试。',
  origin_forbidden: '当前地址不允许访问后台，请检查访问地址。',
  admin_unavailable: '后台暂时不可用，请稍后重试。',
  invalid_request: '请求内容不正确，请检查后重试。',
  file_too_large: '图片不能超过 10 MiB。',
  unsupported_image: '请选择静态 PNG、JPEG 或 WebP 图片。',
  invalid_image: '图片无法读取或超过尺寸限制，请重新选择。',
  file_not_found: '图片不存在。',
  upload_unavailable: '图片服务暂时不可用，请稍后重试。',
  network_error: '暂时无法连接后台，请稍后重试。',
  unexpected_response: '后台响应异常，请稍后重试。',
}
export class AdminApiError extends Error {
  constructor(code, status = 0) {
    super(messages[code] || messages.unexpected_response)
    this.name = 'AdminApiError'
    this.code = Object.hasOwn(messages, code) ? code : 'unexpected_response'
    this.status = status
  }
}
function sessionPayload(value) {
  if (value?.authenticated === false && value.admin === null && value.csrf_token === null && value.expires_at === null) return value
  if (value?.authenticated === true && value.admin?.id === 1 && typeof value.admin.username === 'string' &&
      value.admin.username.length > 0 && typeof value.csrf_token === 'string' && value.csrf_token.length >= 16 &&
      typeof value.expires_at === 'string' && Number.isFinite(Date.parse(value.expires_at))) return value
  throw new AdminApiError('unexpected_response')
}
export function createAdminApi(fetchImpl = (...args) => globalThis.fetch(...args)) {
  async function request(path, { method = 'GET', body, csrf } = {}) {
    const form = typeof FormData !== 'undefined' && body instanceof FormData
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 10000)
    const headers = { Accept: 'application/json' }
    if (method !== 'GET') {
      if (!form) headers['Content-Type'] = 'application/json'
      headers['X-Admin-Request'] = '1'
      if (csrf) headers['X-CSRF-Token'] = csrf
    }
    try {
      const response = await fetchImpl('/api/admin/' + path, {
        method, credentials: 'same-origin', cache: 'no-store', headers,
        signal: controller.signal, ...(body === undefined ? {} : { body: form ? body : JSON.stringify(body) }),
      })
      let value
      try { value = await response.json() } catch { value = null }
      if (!response.ok) {
        const fallback = response.status === 401 ? 'unauthenticated' : response.status === 503 ? 'admin_unavailable' : 'unexpected_response'
        throw new AdminApiError(value?.error?.code || fallback, response.status)
      }
      return value
    } catch (error) {
      if (error instanceof AdminApiError) throw error
      throw new AdminApiError('network_error')
    } finally { clearTimeout(timeout) }
  }
  function toolPayload(value) {
    try { return parseToolSettings(value) } catch { throw new AdminApiError('unexpected_response') }
  }
  return {
    projects: () => request('projects'),
    project: id => request('projects/' + id),
    createProject: (value, csrf) => request('projects', {method:'POST', body:value, csrf}),
    saveProject: (id, value, csrf) => request('projects/' + id, {method:'PUT', body:value, csrf}),
    publishProject: (id, csrf) => request('projects/' + id + '/publish', {method:'POST', body:{}, csrf}),
    archiveProject: (id, csrf) => request('projects/' + id + '/archive', {method:'POST', body:{}, csrf}),
    reorderProjects: (ids, csrf) => request('projects/order', {method:'PUT', body:{ids}, csrf}),
    profile: () => request('profile'),
    saveProfile: (value, csrf) => request('profile', {method:'PUT', body:value, csrf}),
    tools: async () => toolPayload(await request('tools')),
    saveTools: async (value, csrf) => toolPayload(await request('tools', { method:'PUT', body:value, csrf })),
    uploadFile: async (file, csrf) => {
      const body = new FormData(); body.append('file', file)
      const value = await request('files', { method:'POST', body, csrf })
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value?.id) ||
          !['image/png','image/jpeg','image/webp'].includes(value.media_type) ||
          !Number.isInteger(value.byte_size) || value.byte_size < 1 || value.byte_size > 10485760 ||
          !Number.isInteger(value.width) || !Number.isInteger(value.height) || value.width < 1 || value.height < 1 ||
          value.width * value.height > 40000000 || value.url !== '/api/admin/files/' + value.id) throw new AdminApiError('unexpected_response')
      return value
    },
    session: async () => sessionPayload(await request('session')),
    login: async (username, password, csrf) => {
      const value = sessionPayload(await request('login', { method: 'POST', body: { username, password }, csrf }))
      if (!value.authenticated) throw new AdminApiError('unexpected_response')
      return value
    },
    logout: async csrf => {
      const value = sessionPayload(await request('logout', { method: 'POST', body: {}, csrf }))
      if (value.authenticated) throw new AdminApiError('unexpected_response')
      return value
    },
    overview: async () => {
      const value = await request('overview')
      if (value?.admin?.id !== 1 || !Array.isArray(value.modules)) throw new AdminApiError('unexpected_response')
      return value
    },
  }
}
