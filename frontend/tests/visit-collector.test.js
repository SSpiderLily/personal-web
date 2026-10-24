import test from 'node:test'
import assert from 'node:assert/strict'
import { createVisitCollector } from '../src/statistics/visitCollector.js'

const response = (body = { recorded: true }, ok = true) => ({ ok, json: async () => body })
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const turn = () => new Promise(resolve => setImmediate(resolve))

// A shared lock double preserves exclusive callback ownership through JSON parsing.
function exclusiveLocks() {
  let tail = Promise.resolve()
  const calls = []
  return { calls, request(name, options, callback) {
    calls.push({ name, options })
    const operation = tail.then(() => {
      if (options.signal.aborted) throw new Error('aborted')
      return callback()
    })
    tail = operation.catch(() => {})
    return operation
  } }
}

test('sends only the exact anonymous visit request and returns recorded true or false', async () => {
  const calls = []
  const collector = createVisitCollector({ locks: null, fetchImpl: async (url, options) => {
    calls.push({ url, options }); return response({ recorded: calls.length === 1 })
  } })
  assert.equal(await collector.website(), true)
  assert.equal(await collector.project(42), false)
  assert.deepEqual(calls.map(call => call.url), ['/api/admin/visits', '/api/admin/visits'])
  assert.deepEqual(calls.map(call => JSON.parse(call.options.body)), [{ kind: 'website' }, { kind: 'project', project_id: 42 }])
  for (const { options } of calls) {
    assert.deepEqual(Object.keys(options).sort(), ['body', 'cache', 'credentials', 'headers', 'method', 'signal'])
    assert.equal(options.method, 'POST')
    assert.equal(options.credentials, 'same-origin')
    assert.equal(options.cache, 'no-store')
    assert.deepEqual(options.headers, { 'Content-Type': 'application/json', 'X-Admin-Request': '1' })
    assert.ok(options.signal instanceof AbortSignal)
  }
})

test('website is attempted once even after failure; project opens are never permanently cached', async () => {
  const bodies = []
  const collector = createVisitCollector({ locks: null, fetchImpl: async (_, options) => {
    bodies.push(JSON.parse(options.body)); if (bodies.length === 1) throw new Error('offline'); return response()
  } })
  assert.equal(await collector.website(), false)
  assert.equal(await collector.website(), false)
  assert.equal(await collector.project(7), true)
  assert.equal(await collector.project(7), true)
  assert.deepEqual(bodies, [{ kind: 'website' }, { kind: 'project', project_id: 7 }, { kind: 'project', project_id: 7 }])
})

test('rejects invalid project IDs without sending a request', async () => {
  let calls = 0
  const collector = createVisitCollector({ locks: null, fetchImpl: async () => { calls++; return response() } })
  for (const id of [undefined, null, 0, -1, 1.5, '1', NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, {}, 1n]) assert.equal(await collector.project(id), false)
  assert.equal(calls, 0)
  assert.equal(await collector.project(Number.MAX_SAFE_INTEGER), true)
})

test('same-page queue waits through response parsing before sending the next request', async () => {
  const parsed = deferred(); const calls = []
  const collector = createVisitCollector({ locks: null, fetchImpl: async (_, options) => {
    calls.push(JSON.parse(options.body)); return calls.length === 1 ? { ok: true, json: () => parsed.promise } : response()
  } })
  const first = collector.website(); const second = collector.project(1)
  await turn(); assert.equal(calls.length, 1)
  parsed.resolve({ recorded: true })
  assert.deepEqual(await Promise.all([first, second]), [true, true])
  assert.equal(calls.length, 2)
})

test('every visit uses the shared exclusive lock, held through parsing across collector instances', async () => {
  const locks = exclusiveLocks(); const parsed = deferred(); const calls = []
  const fetchImpl = async (_, options) => { calls.push(JSON.parse(options.body)); return calls.length === 1 ? { ok: true, json: () => parsed.promise } : response() }
  const one = createVisitCollector({ locks, fetchImpl }); const two = createVisitCollector({ locks, fetchImpl })
  const first = one.website(); const second = two.project(3)
  await turn(); assert.equal(calls.length, 1)
  parsed.resolve({ recorded: true })
  assert.deepEqual(await Promise.all([first, second]), [true, true])
  assert.equal(await one.project(3), true)
  assert.equal(locks.calls.length, 3)
  for (const call of locks.calls) {
    assert.equal(call.name, 'personal-web-visits-v1'); assert.equal(call.options.mode, 'exclusive')
    assert.ok(call.options.signal instanceof AbortSignal)
  }
})

for (const [label, fail] of [
  ['HTTP error', () => response({ recorded: true }, false)],
  ['network rejection', () => Promise.reject(new Error('offline'))],
  ['synchronous fetch throw', () => { throw new Error('offline') }],
  ['bad JSON', () => ({ ok: true, json: async () => { throw new Error('json') } })],
  ...[null, {}, { recorded: 1 }, { recorded: 'true' }, { recorded: true, extra: 1 }, []].map(body => [`malformed response ${JSON.stringify(body)}`, () => response(body)]),
]) test(`${label} resolves false and allows the next queued request`, async () => {
  let calls = 0
  const collector = createVisitCollector({ locks: null, fetchImpl: () => ++calls === 1 ? fail() : response() })
  assert.deepEqual(await Promise.all([collector.website(), collector.project(1)]), [false, true])
  assert.equal(calls, 2)
})

test('lock rejection never resends unlocked and does not block later requests', async () => {
  let lockCalls = 0, fetchCalls = 0
  const locks = { request: (_, options, callback) => { assert.ok(options.signal); if (++lockCalls === 1) throw new Error('lock failed'); return callback() } }
  const collector = createVisitCollector({ locks, fetchImpl: async () => { fetchCalls++; return response() } })
  assert.deepEqual(await Promise.all([collector.website(), collector.project(1)]), [false, true])
  assert.equal(lockCalls, 2); assert.equal(fetchCalls, 1)
})

test('lock waiting times out, aborts its signal, and ignores a late callback', async () => {
  let lateCallback, firstSignal, calls = 0, lockCalls = 0
  const locks = { request: (_, { signal }, callback) => {
    if (++lockCalls === 1) { firstSignal = signal; lateCallback = callback; return new Promise(() => {}) }
    return callback()
  } }
  const collector = createVisitCollector({ locks, timeoutMs: 20, fetchImpl: async () => { calls++; return response() } })
  assert.deepEqual(await Promise.all([collector.website(), collector.project(1)]), [false, true])
  assert.equal(firstSignal.aborted, true)
  await lateCallback(); assert.equal(calls, 1)
})

test('fetch timeout aborts the same lock signal and advances the queue without retry', async () => {
  let firstSignal, calls = 0
  const locks = { request: (_, { signal }, callback) => { if (!firstSignal) firstSignal = signal; return callback() } }
  const collector = createVisitCollector({ locks, timeoutMs: 20, fetchImpl: (_, { signal }) => {
    if (++calls === 1) { assert.equal(signal, firstSignal); return new Promise(() => {}) }
    return response()
  } })
  assert.deepEqual(await Promise.all([collector.website(), collector.project(1)]), [false, true])
  assert.equal(firstSignal.aborted, true); assert.equal(calls, 2)
})

test('response parsing is inside the total timeout budget and late parsing is ignored', async () => {
  const parsed = deferred(); let calls = 0
  const collector = createVisitCollector({ locks: null, timeoutMs: 20, fetchImpl: async () => ++calls === 1 ? { ok: true, json: () => parsed.promise } : response() })
  assert.deepEqual(await Promise.all([collector.website(), collector.project(1)]), [false, true])
  parsed.resolve({ recorded: true }); await turn(); assert.equal(calls, 2)
})

test('default total budget is 5000ms, including the time spent waiting for a lock', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let callback, signal, settled = false, calls = 0
  const locks = { request: (_, options, fn) => { signal = options.signal; callback = fn; return new Promise(() => {}) } }
  const collector = createVisitCollector({ locks, fetchImpl: async () => { calls++; return response() } })
  const result = collector.website().then(value => { settled = true; return value })
  await Promise.resolve(); t.mock.timers.tick(4999); await Promise.resolve()
  assert.equal(settled, false); assert.equal(signal.aborted, false)
  t.mock.timers.tick(1); assert.equal(await result, false); assert.equal(signal.aborted, true)
  await callback(); assert.equal(calls, 0)
})

test('dispose aborts in-flight fetch, resolves queued calls false, and prevents future requests', async () => {
  const fetched = deferred(); let signal, calls = 0
  const collector = createVisitCollector({ locks: null, fetchImpl: (_, options) => { calls++; signal = options.signal; return fetched.promise } })
  const first = collector.website(); const second = collector.project(2)
  await turn(); collector.dispose(); collector.dispose()
  assert.deepEqual(await Promise.all([first, second, collector.project(3), collector.website()]), [false, false, false, false])
  assert.equal(signal.aborted, true)
  fetched.resolve(response()); await turn(); assert.equal(calls, 1)
})

test('dispose during lock waiting cancels all work and prevents late lock callback fetch', async () => {
  let callback, signal, calls = 0
  const locks = { request: (_, options, fn) => { signal = options.signal; callback = fn; return new Promise(() => {}) } }
  const collector = createVisitCollector({ locks, fetchImpl: async () => { calls++; return response() } })
  const first = collector.website(); const second = collector.project(2)
  await turn(); collector.dispose()
  assert.deepEqual(await Promise.all([first, second]), [false, false]); assert.equal(signal.aborted, true)
  await callback(); assert.equal(calls, 0)
})

test('dispose during parsing ignores a later success and consumes a later rejection', async () => {
  const parsed = deferred()
  const collector = createVisitCollector({ locks: null, fetchImpl: async () => ({ ok: true, json: () => parsed.promise }) })
  const result = collector.website(); await turn(); collector.dispose()
  assert.equal(await result, false)
  parsed.reject(new Error('late failure')); await turn()
})
