// Return to the current route when an open editor postpones navigation.
export function allowPageNavigation(browserWindow, currentPage, nextPage) {
  if (currentPage === nextPage) return true
  const event = new CustomEvent('site-before-navigate', {
    cancelable: true,
    detail: { hash: browserWindow.location.hash },
  })
  if (browserWindow.dispatchEvent(event)) return true
  browserWindow.history.replaceState(null, '', `#/${currentPage}`)
  return false
}
