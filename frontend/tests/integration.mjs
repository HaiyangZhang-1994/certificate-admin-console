// Real Vite proxy + FastAPI only. Mutates the seeded local demo database.
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright')
const origin = process.env.FRONTEND_URL ?? 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE } : {}) })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(10000)
const errors = []
const submissions = []
page.on('pageerror', error => errors.push(error.message))
page.on('console', message => {
  if (message.type() === 'warning' || (message.type() === 'error' && !/Failed to load resource:|net::ERR_/.test(message.text()))) errors.push(message.text())
})
page.on('request', request => {
  if (request.url().endsWith('/issue-certificates')) submissions.push(request.headers()['idempotency-key'])
})
const visible = text => page.getByText(text, { exact: false }).first().waitFor()
const search = page.getByRole('textbox', { name: 'Search learner or certificate' })
const batch = () => page.getByRole('dialog', { name: 'Issue certificates' })
async function get(url) {
  const response = await context.request.get(origin + url)
  assert.equal(response.status(), 200, url)
  return response.json()
}
async function post(url, key) {
  return context.request.post(origin + url, { headers: { Origin: origin, ...(key ? { 'Idempotency-Key': key } : {}) } })
}
async function login(username) {
  await page.getByLabel('Username', { exact: true }).fill(username)
  await page.getByLabel('Password', { exact: true }).fill('DemoPass123!')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await visible(username === 'sydney.admin' ? 'Sydney Training' : 'Perth Training')
  await page.locator('.table-footer').waitFor()
}
async function selectCourse(title) {
  await batch().getByText('Refreshing course eligibility…', { exact: true }).waitFor({ state: 'hidden' })
  await batch().locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: title, exact: true }).click()
}
async function openBatch(title = 'Workplace Safety') {
  await page.getByRole('button', { name: 'Issue certificates', exact: true }).first().click()
  await selectCourse(title)
}
async function closeBatch() {
  await batch().getByRole('button', { name: 'Close this dialog' }).click()
  await batch().waitFor({ state: 'hidden' })
}
async function shot(name) {
  if (!process.env.SCREENSHOT_DIR) return
  await mkdir(process.env.SCREENSHOT_DIR, { recursive: true })
  await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `${name}.png`), fullPage: false })
}
async function download(expected, timezoneOffset) {
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  const file = await pending
  assert.equal(await file.failure(), null)
  const data = await readFile(await file.path())
  assert.deepEqual([...data.subarray(0, 3)], [239, 187, 191])
  const text = data.toString('utf8')
  assert.match(text, /learner_name,course_title,serial_number,issue_date/)
  // The seed deliberately includes quoted multiline names; line count is not row count.
  assert.deepEqual(text.match(/CERT-[0-9a-f-]{36}/g) ?? [], expected.items.map(row => row.serial_number))
  if (expected.total) assert.ok(text.includes(timezoneOffset))
  assert.equal(new URL(file.url()).searchParams.has('page'), false)
  assert.equal(new URL(file.url()).searchParams.has('page_size'), false)
  return text
}
try {
  await page.goto(origin)
  assert.equal(new URL(page.url()).origin, origin)
  assert.match(await page.title(), /Certificate Admin/)
  assert.equal(await page.getByText('Development mock mode').count(), 0)
  await login('sydney.admin')
  const initial = await get('/api/certificates?page_size=100')
  assert.ok(initial.total >= 25, 'Run npm run seed first')
  await visible(`Total ${initial.total} certificates`)
  await page.reload(); await visible(`Total ${initial.total} certificates`)
  await page.locator('.el-pager .number').filter({ hasText: /^2$/ }).click()
  await page.locator('.el-pager .is-active').filter({ hasText: /^2$/ }).waitFor()
  await search.fill('Alex Chen'); await visible('Total 1 certificates')
  assert.equal(await page.locator('.el-pager .is-active').innerText(), '1')
  await search.fill(initial.items[0].serial_number); await visible('Total 1 certificates')
  await search.fill('no-such-certificate'); await visible('No matching certificates')
  await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click()
  await visible(`Total ${initial.total} certificates`)
  await page.locator('.filters .el-select__wrapper').first().click()
  await page.getByRole('option', { name: 'Empty Course', exact: true }).click()
  await visible('No matching certificates')
  await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click()
  await visible(`Total ${initial.total} certificates`)
  await page.getByRole('columnheader', { name: 'Learner' }).click()
  await page.locator('.table-footer').waitFor()
  const all = await get('/api/certificates?page_size=100&sort_by=learner_name&sort_order=asc')
  const csv = await download(all, '+11:00')
  assert.ok(csv.includes('中文') && csv.includes('""Learner""') && csv.includes("' =HYPERLINK"))
  console.log('PASS real login/restoration, name/serial search, pagination reset, sorting, empty search, all-page CSV with escaping and timezone')

  const courses = (await get('/api/courses')).items
  const course = courses.find(item => item.title === 'Workplace Safety')
  await openBatch('Future Course'); await visible('This course has not finished')
  assert.equal(await batch().getByRole('button', { name: 'Issue certificates', exact: true }).isDisabled(), true)
  await selectCourse('Workplace Safety')
  // Lose the real committed response, then recover it through the UI with the original key.
  let committed
  await page.route('**/issue-certificates', async route => {
    const response = await route.fetch()
    assert.equal(response.status(), 200)
    committed = await response.json()
    await new Promise(resolve => setTimeout(resolve, 500))
    await route.abort('failed')
  })
  const before = submissions.length
  const submit = batch().getByRole('button', { name: 'Issue certificates', exact: true })
  await submit.evaluate(button => { button.click(); button.click() })
  await visible('Processing course enrollments')
  assert.equal(await batch().locator('.dialog-actions button').isDisabled(), true)
  await visible('Result not yet confirmed')
  assert.equal(submissions.length, before + 1)
  const key = submissions.at(-1)
  assert.equal(committed.issued_count, course.eligible_count)
  assert.equal(committed.results.length, course.enrollment_count)
  await page.unroute('**/issue-certificates')
  await closeBatch(); await page.reload(); await page.locator('.table-footer').waitFor()
  await openBatch(); await visible('A previous batch is awaiting confirmation')
  await batch().getByRole('button', { name: 'Retry original batch' }).click(); await visible('Batch completed')
  assert.equal(submissions.at(-1), key)
  const replay = await post(`/api/courses/${course.id}/issue-certificates`, key)
  assert.equal(replay.status(), 200); assert.deepEqual(await replay.json(), committed)
  await shot('real-batch')
  await batch().getByRole('button', { name: 'Start a new batch' }).click()
  await batch().getByRole('button', { name: 'Issue certificates', exact: true }).click(); await visible('Batch completed')
  assert.notEqual(submissions.at(-1), key)
  const repeated = await post(`/api/courses/${course.id}/issue-certificates`, submissions.at(-1))
  assert.equal((await repeated.json()).issued_count, 0)
  await closeBatch()
  console.log('PASS real issuance, double-click guard, committed-response loss, reload/original-key replay, new-key duplicate submission')

  const current = await get('/api/certificates?page_size=100&status=valid')
  const target = current.items[0]
  await search.fill(target.serial_number); await visible('Total 1 certificates')
  await page.getByRole('button', { name: `View certificate for ${target.learner.name}` }).click()
  const drawer = page.getByRole('dialog', { name: 'Certificate details' })
  await drawer.getByText('Sydney Admin', { exact: true }).waitFor()
  await drawer.getByRole('button', { name: 'Revoke certificate', exact: true }).click()
  await page.getByRole('button', { name: 'Keep certificate' }).click()
  await drawer.getByRole('button', { name: 'Revoke certificate', exact: true }).click()
  await page.getByRole('dialog', { name: 'Revoke certificate' }).getByRole('button', { name: 'Revoke certificate', exact: true }).click()
  await drawer.getByText('This certificate has been revoked', { exact: false }).waitFor()
  const revoked = await get(`/api/certificates/${target.id}`)
  assert.equal(revoked.status, 'revoked')
  const again = await post(`/api/certificates/${target.id}/revoke`)
  assert.deepEqual(await again.json(), revoked)
  await drawer.getByRole('button', { name: 'Close this dialog' }).click()
  await page.locator('.filters .el-select__wrapper').nth(1).click()
  await page.getByRole('option', { name: 'Revoked', exact: true }).click()
  await visible('Total 1 certificates')
  await download({ total: 1, items: [revoked] }, '+11:00')
  await shot('real-filtered')
  console.log('PASS real detail, revoke cancel/confirm, repeated revoke, filtered CSV')

  await page.getByRole('button', { name: 'Sign out' }).click(); await login('perth.admin')
  assert.equal(await search.inputValue(), '')
  assert.equal(await page.getByRole('dialog').count(), 0)
  await visible('Australia/Perth')
  // Element Plus removes closed messages after its leave transition, not synchronously.
  await page.waitForFunction(() => document.querySelectorAll('.el-message').length === 0, undefined, { timeout: 1500 })
  const perth = await get('/api/certificates?page_size=100')
  assert.equal(perth.total, 2)
  assert.equal((await context.request.get(`${origin}/api/certificates/${target.id}`)).status(), 404)
  assert.equal((await post(`/api/certificates/${target.id}/revoke`)).status(), 404)
  assert.equal((await post(`/api/courses/${course.id}/issue-certificates`, crypto.randomUUID())).status(), 404)
  assert.equal((await context.request.get(`${origin}/api/certificates/export.csv?course_id=${course.id}`)).status(), 404)
  await download(perth, '+08:00')
  await page.waitForFunction(() => document.querySelectorAll('.el-message').length === 0)
  await shot('real-desktop')
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await shot('real-mobile')
  assert.equal(await page.locator('vite-error-overlay').count(), 0)
  assert.deepEqual(errors, [])
  console.log('PASS tenant switch/private-state cleanup, cross-tenant read/write/export denial, Perth CSV, desktop/mobile, no runtime errors or overlays')
  await post('/api/auth/logout')
  await search.fill('expired-session')
  await visible('Your session has expired. Please sign in again.')
  assert.equal(await page.getByText('Perth Training', { exact: true }).count(), 0)
  console.log('PASS real invalidated session returns 401 and clears private UI')
} catch (error) {
  await shot('real-failure')
  console.error(await page.locator('body').innerText())
  throw error
} finally { await browser.close() }
