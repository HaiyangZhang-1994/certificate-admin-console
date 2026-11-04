import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source = readFileSync(new URL('../src/model.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const { exportUrl, batchStorageKey, formatDate, checked, RequestError, uncertain } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('CSV preserves filters, encodes literal search and excludes pagination', () => {
  const url = new URL(exportUrl({ q: '张 %_ &', status: 'revoked', course_id: 'course', sort_by: 'learner_name', sort_order: 'asc', page: 3, page_size: 20 }), 'http://127.0.0.1')
  assert.equal(url.pathname, '/api/certificates/export.csv')
  assert.equal(url.searchParams.get('q'), '张 %_ &')
  assert.equal(url.searchParams.get('status'), 'revoked')
  assert.equal(url.searchParams.get('sort_by'), 'learner_name')
  assert.equal(url.searchParams.has('page'), false)
  assert.equal(url.searchParams.has('page_size'), false)
  assert.equal(new URL(exportUrl({ q: '', course_id: undefined }), 'http://127.0.0.1').search, '')
})
test('pending issuance keys are isolated by tenant, administrator and course', () => {
  const user = { admin: { id: 'a' }, tenant: { id: 't' } }
  const key = batchStorageKey(user, 'c')
  assert.notEqual(key, batchStorageKey({ ...user, admin: { id: 'b' } }, 'c'))
  assert.notEqual(key, batchStorageKey({ ...user, tenant: { id: 'u' } }, 'c'))
  assert.notEqual(key, batchStorageKey(user, 'd'))
  assert.equal(key, batchStorageKey(user, 'c'))
})
test('tenant date formatting observes Sydney DST and Perth zone', () => {
  assert.match(formatDate('2026-10-20T23:30:00Z', 'Australia/Sydney'), /21 Oct 2026.*10:30/)
  assert.match(formatDate('2026-10-20T23:30:00Z', 'Australia/Perth'), /21 Oct 2026.*07:30/)
  assert.match(formatDate('2026-06-20T23:30:00Z', 'Australia/Sydney'), /21 June 2026.*09:30/)
})
test('HTTP status governs success, not the presence of a data envelope', async () => {
  await assert.rejects(checked(Promise.resolve({ data: { ok: true }, error: { error: { code: 'course_not_finished', message: 'Not finished' } }, response: new Response('', { status: 409 }) })), error => error.status === 409 && error.message === 'Not finished')
  assert.deepEqual(await checked(Promise.resolve({ data: { failed_count: 1 }, response: new Response() })), { failed_count: 1 })
})
test('network, 503 and malformed responses remain uncertain; deterministic 4xx do not', async () => {
  await assert.rejects(checked(Promise.reject(new TypeError('Failed to fetch'))), error => error.status === 0 && uncertain(error))
  await assert.rejects(checked(Promise.resolve({ response: new Response() })), error => error.status === 500 && uncertain(error))
  assert.equal(uncertain(new RequestError('busy', 503)), true)
  assert.equal(uncertain(new RequestError('conflict', 409)), false)
  assert.equal(uncertain(new RequestError('expired', 401)), false)
})
