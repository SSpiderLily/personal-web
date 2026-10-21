export async function requestDiceValue({ fetchImpl = fetch, signal } = {}) {
  const timeout = AbortSignal.timeout(8000)
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
  requestSignal.throwIfAborted()
  const response = await fetchImpl('/api/dice/roll', { method: 'POST', signal: requestSignal })
  if (!response.ok) throw new Error('Dice request failed')
  const result = await response.json()
  requestSignal.throwIfAborted()
  if (!Number.isInteger(result?.value) || result.value < 1 || result.value > 6) {
    throw new Error('Invalid dice response')
  }
  return result.value
}
