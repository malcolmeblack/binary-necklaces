const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

const code = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, '../app/chat-api.ts'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
).outputText

function client(fetch, fireTimeout = 0) {
  const context = {
    exports: {}, fetch, AbortController,
    setTimeout(callback, milliseconds) {
      const timer = { cancelled: false }
      if (milliseconds < 25000 || milliseconds === fireTimeout) {
        queueMicrotask(() => { if (!timer.cancelled) callback() })
      }
      return timer
    },
    clearTimeout(timer) { timer.cancelled = true },
  }
  vm.runInNewContext(code, context)
  return context.exports.askQuestion
}

function json(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, statusText: '', json: async () => body }
}

const accepted = () => json({ jobId: 'example-job', token: 'private-token', expiresAt: 9999999999 }, 202)
const signal = () => new AbortController().signal

test('same-origin job transport deduplicates events and returns the answer', async () => {
  const calls = []
  const statuses = []
  const responses = [
    accepted(),
    json({ status: 'queued', events: [] }),
    json({ status: 'running', events: [{ seq: 1, status: 'first_responder' }] }),
    json({ status: 'done', events: [{ seq: 1, status: 'first_responder' }, { seq: 2, status: 'skeptic' }], response: 'Answer' }),
  ]
  const ask = client(async (url, options) => {
    calls.push({ url, options })
    return responses.shift()
  })
  assert.equal(await ask('Question?', status => statuses.push(status), signal()), 'Answer')
  assert.deepEqual(statuses, ['first_responder', 'skeptic'])
  assert.equal(calls[0].url, '/api/chatbot')
  assert.equal(calls[0].options.method, 'POST')
  assert.deepEqual(JSON.parse(calls[0].options.body), { query: 'Question?' })
  for (const call of calls.slice(1)) {
    assert.equal(call.url, '/api/chatbot/example-job')
    assert.equal(call.options.headers.Authorization, 'Bearer private-token')
    assert.equal(call.options.cache, 'no-store')
  }
})

test('a transient polling error is retried without resubmitting the question', async () => {
  let posts = 0, gets = 0
  const ask = client(async (url, options) => {
    if (options.method === 'POST') { posts++; return accepted() }
    if (++gets === 1) return json({ error: 'Temporarily unavailable' }, 503)
    return json({ status: 'done', response: 'Answer' })
  })
  assert.equal(await ask('Q', () => {}, signal()), 'Answer')
  assert.equal(posts, 1)
  assert.equal(gets, 2)
})

test('submission failures are not retried', async () => {
  let calls = 0
  const ask = client(async () => { calls++; return json({ error: 'Unavailable' }, 503) })
  await assert.rejects(ask('Q', () => {}, signal()), /Unavailable/)
  assert.equal(calls, 1)
})

test('permanent polling errors are not retried', async () => {
  let calls = 0
  const ask = client(async () => ++calls === 1 ? accepted() : json({ error: 'Expired' }, 410))
  await assert.rejects(ask('Q', () => {}, signal()), /Expired/)
  assert.equal(calls, 2)
})

test('backend failure is returned as an error', async () => {
  let calls = 0
  const ask = client(async () => ++calls === 1 ? accepted() : json({ status: 'error', error: 'Unable to answer' }))
  await assert.rejects(ask('Q', () => {}, signal()), /Unable to answer/)
})

test('malformed accepted and completed responses fail promptly', async () => {
  await assert.rejects(client(async () => json(null))('Q', () => {}, signal()), /Invalid response/)
  let calls = 0
  const ask = client(async () => ++calls === 1 ? accepted() : json({ status: 'done' }))
  await assert.rejects(ask('Q', () => {}, signal()), /Invalid response/)
})

test('unmount cancellation aborts an in-flight status request', async () => {
  const controller = new AbortController()
  let calls = 0
  const ask = client(async (url, options) => {
    if (++calls === 1) return accepted()
    return new Promise((resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true })
      queueMicrotask(() => controller.abort(new Error('Unmounted')))
    })
  })
  await assert.rejects(ask('Q', () => {}, controller.signal), /Unmounted/)
  assert.equal(calls, 2)
})

test('the overall deadline stops the job even when no completion is received', async () => {
  const ask = client(async (url, options) => {
    if (options.signal.aborted) throw options.signal.reason
    return accepted()
  }, 285000)
  await assert.rejects(ask('Q', () => {}, signal()), /response timed out/)
})
