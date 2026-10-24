const messages = {
  invalid_credentials: '账号或密码不正确，请重试。',
  unauthenticated: '登录已失效，请重新登录。',
  csrf_failed: '会话验证失败，请刷新页面后重试。',
  origin_forbidden: '当前地址不允许访问后台，请检查访问地址。',
  admin_unavailable: '后台暂时不可用，请稍后重试。',
  invalid_request: '请检查账号和密码输入。',
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
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 10000)
    const headers = { Accept: 'application/json' }
    if (method !== 'GET') {
      headers['Content-Type'] = 'application/json'
      headers['X-Admin-Request'] = '1'
      if (csrf) headers['X-CSRF-Token'] = csrf
    }
    try {
      const response = await fetchImpl('/api/admin/' + path, {
        method, credentials: 'same-origin', cache: 'no-store', headers,
        signal: controller.signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }),
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
  return {
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
