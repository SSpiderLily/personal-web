const LOCK_NAME = 'personal-web-visits-v1'

export function createVisitCollector({
  fetchImpl = globalThis.fetch?.bind(globalThis),
  locks = globalThis.navigator?.locks,
  timeoutMs = 5000,
} = {}) {
  let disposed = false
  let websiteAttempted = false
  let activeController = null
  let draining = false
  const queue = []

  async function record(body) {
    const controller = new AbortController()
    activeController = controller
    const { signal } = controller
    let onAbort
    const cancelled = new Promise(resolve => {
      onAbort = () => resolve(false)
      signal.addEventListener('abort', onAbort, { once: true })
    })
    // One budget covers acquiring the lock, fetching, and parsing its response.
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    const send = async () => {
      if (disposed || signal.aborted) return false
      const response = await fetchImpl('/api/admin/visits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Request': '1' },
        credentials: 'same-origin',
        cache: 'no-store',
        body: JSON.stringify(body),
        signal,
      })
      if (disposed || signal.aborted || !response.ok) return false
      const value = await response.json()
      return !disposed && !signal.aborted && value !== null &&
        typeof value === 'object' && !Array.isArray(value) &&
        Object.keys(value).length === 1 && typeof value.recorded === 'boolean'
        ? value.recorded : false
    }
    try {
      // Only lack of Web Locks permits fallback. Rejected locks must not resend.
      const operation = locks == null
        ? send()
        : locks.request(LOCK_NAME, { mode: 'exclusive', signal }, send)
      return await Promise.race([operation, cancelled]) === true
    } catch {
      return false
    } finally {
      clearTimeout(timer)
      signal.removeEventListener('abort', onAbort)
      if (activeController === controller) activeController = null
    }
  }

  async function drain() {
    draining = true
    try {
      while (!disposed && queue.length) {
        const item = queue.shift()
        item.resolve(await record(item.body))
      }
    } finally {
      draining = false
    }
  }

  function enqueue(body) {
    if (disposed) return Promise.resolve(false)
    return new Promise(resolve => {
      queue.push({ body, resolve })
      if (!draining) void drain()
    })
  }

  return {
    website() {
      if (websiteAttempted || disposed) return Promise.resolve(false)
      websiteAttempted = true
      return enqueue({ kind: 'website' })
    },
    project(id) {
      if (!Number.isSafeInteger(id) || id <= 0) return Promise.resolve(false)
      return enqueue({ kind: 'project', project_id: id })
    },
    dispose() {
      disposed = true
      activeController?.abort()
      for (const item of queue.splice(0)) item.resolve(false)
    },
  }
}
