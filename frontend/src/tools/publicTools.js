import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

export function parseToolSettings(value) {
  if (!Array.isArray(value?.tools) || value.tools.length !== 10) throw new Error('Invalid tool settings')
  const seen = new Set(), orders = new Set()
  const tools = value.tools.map(tool => {
    const grid = /^grid_0[1-9]$/.test(tool?.tool_key)
    if ((!grid && tool?.tool_key !== 'dice') || seen.has(tool.tool_key) ||
        tool.placement !== (grid ? 'grid' : 'floating') || typeof tool.is_visible !== 'boolean' ||
        !Number.isInteger(tool.sort_order) || tool.sort_order < 0 || tool.sort_order > (grid ? 8 : 0) ||
        (grid && orders.has(tool.sort_order))) throw new Error('Invalid tool settings')
    seen.add(tool.tool_key)
    if (grid) orders.add(tool.sort_order)
    return { tool_key: tool.tool_key, placement: tool.placement, is_visible: tool.is_visible, sort_order: tool.sort_order }
  })
  tools.sort((a,b) => (a.placement === b.placement ? a.sort_order-b.sort_order : a.placement === 'grid' ? -1 : 1))
  return { tools }
}

export function usePublicTools(fetchImpl = (...args) => globalThis.fetch(...args)) {
  const status = ref('loading'), error = ref(''), settings = ref(null)
  let alive = true, controller = null
  const gridItems = computed(() => settings.value?.tools.filter(t => t.placement === 'grid' && t.is_visible) || [])
  const diceVisible = computed(() => settings.value?.tools.some(t => t.tool_key === 'dice' && t.is_visible) || false)
  async function load() {
    if (!alive || controller) return
    controller = new AbortController()
    const current = controller, timer = setTimeout(() => current.abort(), 10000)
    status.value = 'loading'; error.value = ''; settings.value = null
    try {
      const response = await fetchImpl('/api/tools', { credentials:'same-origin',cache:'no-store', signal:current.signal })
      if (!response.ok) throw new Error('Unavailable')
      const value = parseToolSettings(await response.json())
      if (alive) { settings.value = value; status.value = 'ready' }
    } catch {
      if (alive) { error.value = '暂时无法加载小工具，请重试。'; status.value = 'error' }
    } finally { clearTimeout(timer); controller = null }
  }
  onMounted(load)
  onBeforeUnmount(() => { alive = false; controller?.abort() })
  return { status,error,gridItems,diceVisible,load }
}
