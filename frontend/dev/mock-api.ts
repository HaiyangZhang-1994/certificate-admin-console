// Development-only in-memory transport. Never loaded by a production build.
import type { IncomingMessage, ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'
import type { BulkIssueResult, CertificateDetail, Course, Identity } from '@certificate-admin/api-contract'
import { certificateDetail, courses, identity, perthIdentity } from '../src/api/contract-examples'

const sessions = new Map<string, Identity>()
const batches = new Map<string, BulkIssueResult>()
const attempts = new Set<string>()
const records = new Map<string, CertificateDetail[]>()
export function resetMock() { sessions.clear(); batches.clear(); attempts.clear(); records.clear() }
function data(user: Identity) {
  let items = records.get(user.tenant.id)
  if (!items) {
    items = Array.from({ length: user.admin.username === 'sydney.admin' ? 27 : 4 }, (_, index): CertificateDetail => {
      const id = index === 0 && user.admin.username === 'sydney.admin' ? certificateDetail.id : randomUUID()
      const name = index === 0 ? (user.admin.username === 'sydney.admin' ? 'Alex Chen' : 'Perth Learner') : ['Taylor Lee', 'Jordan Smith', 'Casey Nguyen', 'Riley Thompson', 'Morgan Davis'][index % 5] + ` ${index}`
      return { ...certificateDetail, id, serial_number: `CERT-${id}`, learner: { ...certificateDetail.learner, id: randomUUID(), name, email: `learner${index}@example.test` }, issued_by: user.admin,
        status: index % 6 === 2 ? 'revoked' : 'valid', revoked_at: index % 6 === 2 ? '2026-10-21T01:00:00Z' : null, revoked_by: index % 6 === 2 ? user.admin : null }
    })
    records.set(user.tenant.id, items)
  }
  return items
}
function courseList(user: Identity): Course[] {
  const base = courses.items[0]
  if (!base) return []
  const count = data(user).length
  return [{ ...base, enrollment_count: count + 3, completed_count: count + 2, already_issued_count: count, eligible_count: batches.has(`${user.tenant.id}:issued`) ? 0 : 2 },
    { ...base, id: '30000000-0000-4000-8000-000000000002', title: 'Leadership Essentials', ends_at: '2099-01-01T00:00:00Z', is_finished: false, eligible_count: 0 },
    { ...base, id: '30000000-0000-4000-8000-000000000003', title: 'Empty Course', enrollment_count: 0, completed_count: 0, eligible_count: 0, already_issued_count: 0 }]
}
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
export async function mockApi(req: IncomingMessage, res: ServerResponse) {
  const url = new URL(req.url ?? '/', 'http://127.0.0.1:5173')
  const cookie = (name: string) => req.headers.cookie?.split('; ').find(item => item.startsWith(`${name}=`))?.slice(name.length + 1)
  const scenario = cookie('dev_scenario') ?? 'normal'
  const json = (value: unknown, status = 200) => { res.statusCode = status; res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(value)) }
  const fail = (status: number, code: string, message: string) => json({ error: { code, message } }, status)
  await sleep(450)
  if (url.pathname === '/api/auth/login') {
    let raw = ''; for await (const chunk of req) raw += chunk
    const body: unknown = JSON.parse(raw)
    if (typeof body !== 'object' || body === null || !('username' in body) || !('password' in body) || body.password !== 'DemoPass123!' || !['sydney.admin', 'perth.admin'].includes(String(body.username))) return fail(401, 'invalid_credentials', 'Invalid username or password.')
    const user = body.username === 'sydney.admin' ? identity : perthIdentity
    const token = randomUUID(); sessions.set(token, user)
    res.setHeader('Set-Cookie', [`certificate_admin_session=${token}; HttpOnly; Path=/; SameSite=Lax`, 'dev_scenario=normal; Path=/; SameSite=Lax'])
    return json(user)
  }
  const token = cookie('certificate_admin_session') ?? ''
  if (url.pathname === '/api/auth/logout') { sessions.delete(token); res.setHeader('Set-Cookie', 'certificate_admin_session=; Max-Age=0; Path=/'); res.statusCode = 204; return res.end() }
  const user = sessions.get(token)
  if (!user || scenario === 'expired') return fail(401, 'unauthorized', 'Your session has expired.')
  if (url.pathname === '/api/me') return json(user)
  if (url.pathname === '/api/courses') return json({ items: courseList(user) })
  const items = data(user)
  const filtered = () => {
    const q = (url.searchParams.get('q') ?? '').trim().toLowerCase()
    const direction = url.searchParams.get('sort_order') === 'asc' ? 1 : -1
    const field = url.searchParams.get('sort_by') ?? 'issued_at'
    const value = (item: CertificateDetail) => field === 'learner_name' ? item.learner.name : field === 'serial_number' ? item.serial_number : item.issued_at
    return (scenario === 'empty' ? [] : items).filter(item => (!q || `${item.learner.name} ${item.serial_number}`.toLowerCase().includes(q)) && (!url.searchParams.get('status') || item.status === url.searchParams.get('status')) && (!url.searchParams.get('course_id') || item.course.id === url.searchParams.get('course_id'))).sort((a, b) => direction * (value(a).localeCompare(value(b)) || a.id.localeCompare(b.id)))
  }
  if (url.pathname === '/api/certificates/export.csv') {
    const escape = (text: string) => `"${text.replaceAll('"', '""')}"`
    res.setHeader('Content-Type', 'text/csv; charset=utf-8'); res.setHeader('Content-Disposition', 'attachment; filename="certificates.csv"'); res.setHeader('Cache-Control', 'no-store')
    // Mock dates intentionally use an explicit zone, as does the real server contract.
    return res.end('\ufefflearner_name,course_title,serial_number,issue_date\r\n' + filtered().map(item => [item.learner.name, item.course.title, item.serial_number, user.tenant.timezone === 'Australia/Sydney' ? '2026-10-21T10:30:00+11:00' : '2026-10-21T07:30:00+08:00'].map(escape).join(',')).join('\r\n'))
  }
  if (url.pathname === '/api/certificates') {
    if (scenario === 'error') return fail(500, 'internal_error', 'Development scenario: list request failed.')
    const all = filtered(); const page = Number(url.searchParams.get('page') ?? 1); const size = Number(url.searchParams.get('page_size') ?? 20)
    return json({ items: all.slice((page - 1) * size, page * size).map(({ issued_by, revoked_at, revoked_by, ...summary }) => summary), total: all.length, page, page_size: size })
  }
  const match = url.pathname.match(/^\/api\/certificates\/([^/]+)(\/revoke)?$/)
  if (match) {
    const item = items.find(item => item.id === match[1]); if (!item) return fail(404, 'resource_not_found', 'Certificate not found.')
    if (match[2] && item.status === 'valid') { item.status = 'revoked'; item.revoked_at = new Date().toISOString(); item.revoked_by = user.admin }
    return json(item)
  }
  const issue = url.pathname.match(/^\/api\/courses\/([^/]+)\/issue-certificates$/)
  if (issue) {
    const course = courseList(user).find(item => item.id === issue[1]); if (!course) return fail(404, 'resource_not_found', 'Course not found.')
    if (!course.is_finished) return fail(409, 'course_not_finished', 'This course has not finished.')
    const key = `${user.tenant.id}:${user.admin.id}:${issue[1]}:${req.headers['idempotency-key']}`
    if (scenario === 'conflict') return fail(409, 'idempotency_conflict', 'This key belongs to a different request. Resolve the conflict before starting a new batch.')
    if (scenario === 'busy') return fail(503, 'database_busy', 'Database is busy. Retry with the original key.')
    const saved = batches.get(key); if (saved) return json(saved)
    await sleep(700)
    const result: BulkIssueResult = { issued_count: 0, skipped_count: 0, failed_count: 0, results: [] }
    if (course.enrollment_count) {
      if (course.eligible_count) {
        const id = randomUUID(); const cert: CertificateDetail = { ...certificateDetail, id, serial_number: `CERT-${id}`, learner: { id: randomUUID(), name: 'New Graduate', email: 'graduate@example.test' }, issued_by: user.admin, issued_at: new Date().toISOString() }; items.push(cert)
        result.results.push({ enrollment_id: randomUUID(), learner_id: cert.learner.id, learner_name: cert.learner.name, outcome: 'issued', reason: null, certificate_id: id, serial_number: cert.serial_number })
        if (scenario === 'partial') result.results.push({ enrollment_id: randomUUID(), learner_id: randomUUID(), learner_name: 'Sam Wu', outcome: 'failed', reason: 'invalid_enrollment', certificate_id: null, serial_number: null })
        else { const id2 = randomUUID(); const cert2 = { ...cert, id: id2, serial_number: `CERT-${id2}`, learner: { id: randomUUID(), name: 'Jamie Park', email: 'jamie@example.test' } }; items.push(cert2); result.results.push({ enrollment_id: randomUUID(), learner_id: cert2.learner.id, learner_name: cert2.learner.name, outcome: 'issued', reason: null, certificate_id: id2, serial_number: cert2.serial_number }) }
      }
      for (const item of items.filter(item => !result.results.some(row => row.certificate_id === item.id))) result.results.push({ enrollment_id: randomUUID(), learner_id: item.learner.id, learner_name: item.learner.name, outcome: 'skipped', reason: item.status === 'revoked' ? 'certificate_revoked' : 'already_issued', certificate_id: item.id, serial_number: item.serial_number })
      result.results.push({ enrollment_id: randomUUID(), learner_id: randomUUID(), learner_name: 'Incomplete Learner', outcome: 'skipped', reason: 'not_completed', certificate_id: null, serial_number: null })
    }
    result.issued_count = result.results.filter(item => item.outcome === 'issued').length; result.skipped_count = result.results.filter(item => item.outcome === 'skipped').length; result.failed_count = result.results.filter(item => item.outcome === 'failed').length
    result.results.sort((a, b) => a.enrollment_id.localeCompare(b.enrollment_id)); batches.set(key, result)
    batches.set(`${user.tenant.id}:issued`, result)
    if (scenario === 'uncertain' && !attempts.has(key)) {
      attempts.add(key)
      // Begin a JSON response before interrupting it; this prevents Chromium
      // from silently retrying a reused TCP connection without exposing the loss.
      res.setHeader('Content-Type', 'application/json'); res.write('{')
      await sleep(100); return res.destroy()
    }
    return json(result)
  }
  return fail(404, 'resource_not_found', 'Not found.')
}
