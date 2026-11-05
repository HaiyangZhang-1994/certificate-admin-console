// Run against a seeded real backend and Vite proxy, using a disposable database.
// Course responses are intercepted only where noted to exercise stale/error states.
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright')
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE } : {}) })
const origin = process.env.FRONTEND_URL ?? 'http://127.0.0.1:5173'
const errors = []
function observe(page) {
  page.setDefaultTimeout(10000)
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => {
    if (message.type() === 'warning' || (message.type() === 'error' && !/Failed to load resource:|net::ERR_/.test(message.text()))) errors.push(message.text())
  })
}
async function login(page, user = 'sydney.admin') {
  await page.getByLabel('Username', { exact: true }).fill(user)
  await page.getByLabel('Password', { exact: true }).fill('DemoPass123!')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.locator('.table-footer').waitFor()
}
const batch = page => page.getByRole('dialog', { name: 'Issue certificates', exact: true })
async function openBatch(page, title = 'Empty Course') {
  await page.getByRole('button', { name: 'Issue certificates', exact: true }).first().click()
  await batch(page).getByText('Refreshing course eligibility…', { exact: true }).waitFor({ state: 'hidden' })
  await batch(page).locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: title, exact: true }).click()
}
async function closeBatch(page) {
  await batch(page).getByRole('button', { name: 'Close this dialog' }).click()
  await batch(page).waitFor({ state: 'hidden' })
}
async function screenshot(page, name) {
  if (!process.env.SCREENSHOT_DIR) return
  await mkdir(process.env.SCREENSHOT_DIR, { recursive: true })
  await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `${name}.png`) })
}

try {
  for (const transport of ['both', 'storage', 'channel']) {
    const context = await browser.newContext()
    await context.addInitScript(mode => {
      if (mode === 'storage') Object.defineProperty(window, 'BroadcastChannel', { value: undefined })
      if (mode === 'channel') {
        const setItem = Storage.prototype.setItem
        Storage.prototype.setItem = function (key, value) {
          if (key === 'certificate-admin:session-change') throw new Error('Test: storage unavailable')
          return setItem.call(this, key, value)
        }
      }
    }, transport)
    const page = await context.newPage(); observe(page)
    await page.goto(origin); await login(page)
    const other = await context.newPage(); observe(other)
    await other.goto(origin); await other.locator('.table-footer').waitFor()
    const pendingKey = 'certificate-batch:v1:test:pending'
    await page.evaluate(key => sessionStorage.setItem(key, 'preserve-original-key'), pendingKey)
    let release
    const gate = new Promise(resolve => { release = resolve })
    await page.route('**/api/certificates?**', async route => {
      const response = await route.fetch()
      await gate; await route.fulfill({ response })
    })
    const started = page.waitForRequest(request => request.url().includes('/api/certificates?'))
    const responseFinished = page.waitForResponse(response => response.url().includes('/api/certificates?'))
    await page.getByRole('textbox', { name: 'Search learner or certificate' }).fill('Alex')
    await started
    await other.getByRole('button', { name: 'Sign out' }).click()
    await page.getByText('Your account changed in another tab.', { exact: false }).waitFor()
    await login(other, 'perth.admin')
    release(); await responseFinished
    assert.equal(await page.locator('.identity, .table-panel').count(), 0)
    assert.equal(await page.getByRole('dialog').count(), 0)
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), pendingKey), 'preserve-original-key')
    // A login without a preceding UI logout must invalidate the other tab too.
    await login(page)
    await other.getByText('Your account changed in another tab.', { exact: false }).waitFor()
    assert.equal(await other.locator('.identity, .table-panel').count(), 0)
    await page.getByRole('button', { name: 'Issue certificates', exact: true }).first().click()
    await batch(page).waitFor()
    await login(other, 'perth.admin')
    await page.getByText('Your account changed in another tab.', { exact: false }).waitFor()
    assert.equal(await page.getByRole('dialog').count(), 0)
    await screenshot(page, `session-reset-${transport}`)
    if (transport === 'both') {
      // A restoration response captured before a cookie change must not restore
      // the old tenant after the cross-tab notification cleared the screen.
      const restoring = await context.newPage(); observe(restoring)
      let releaseIdentity
      const identityGate = new Promise(resolve => { releaseIdentity = resolve })
      let identityCaptured
      const captured = new Promise(resolve => { identityCaptured = resolve })
      await restoring.route('**/api/me', async route => {
        const response = await route.fetch()
        assert.equal(response.status(), 200)
        identityCaptured()
        await identityGate; await route.fulfill({ response })
      })
      const identityStarted = restoring.waitForRequest(request => request.url().endsWith('/api/me'))
      const identityFinished = restoring.waitForResponse(response => response.url().endsWith('/api/me'))
      await restoring.goto(origin); await identityStarted
      let captureTimeout
      try {
        await Promise.race([captured, new Promise((_, reject) => { captureTimeout = setTimeout(() => reject(new Error('Identity response was not captured')), 10000) })])
      } finally { clearTimeout(captureTimeout) }
      await login(page)
      await restoring.getByText('Your account changed in another tab.', { exact: false }).waitFor()
      releaseIdentity(); await identityFinished
      assert.equal(await restoring.locator('.identity, .table-panel').count(), 0)
    }
    await context.close()
    console.log(`PASS cross-tab login/logout, stale response rejection and pending-key preservation (${transport})`)
  }

  const context = await browser.newContext()
  const page = await context.newPage(); observe(page)
  await page.goto(origin); await login(page)
  const identity = await (await context.request.get(origin + '/api/me')).json()
  const courses = (await (await context.request.get(origin + '/api/courses')).json()).items
  const workplace = courses.find(course => course.title === 'Workplace Safety')
  const empty = courses.find(course => course.title === 'Empty Course')
  const conflictKey = crypto.randomUUID()
  const stored = await context.request.post(origin + `/api/courses/${workplace.id}/issue-certificates`, { headers: { Origin: origin, 'Idempotency-Key': conflictKey } })
  assert.equal(stored.status(), 200)
  const storageKey = `certificate-batch:v1:${identity.tenant.id}:${identity.admin.id}:${empty.id}`
  await page.evaluate(({ storageKey, conflictKey }) => sessionStorage.setItem(storageKey, conflictKey), { storageKey, conflictKey })
  const keys = []
  page.on('request', request => { if (request.url().endsWith('/issue-certificates')) keys.push(request.headers()['idempotency-key']) })
  await openBatch(page)
  await batch(page).getByRole('button', { name: 'Retry original batch' }).click()
  await batch(page).getByText('Idempotency key conflict.', { exact: true }).waitFor()
  await batch(page).getByRole('button', { name: 'Start a new batch', exact: true }).click()
  await page.getByRole('button', { name: 'Keep original key', exact: true }).click()
  assert.equal(await page.evaluate(key => sessionStorage.getItem(key), storageKey), conflictKey)
  await batch(page).getByRole('button', { name: 'Start a new batch', exact: true }).click()
  await page.getByRole('button', { name: 'Start new batch', exact: true }).click()
  await batch(page).getByRole('button', { name: 'Issue certificates', exact: true }).click()
  await batch(page).getByText('No enrollments in this course.', { exact: true }).waitFor()
  assert.notEqual(keys.at(-1), conflictKey)
  await screenshot(page, 'conflict-recovered')
  await batch(page).getByRole('button', { name: 'Start a new batch', exact: true }).click()
  for (const failure of ['network', 'busy']) {
    await page.route('**/issue-certificates', route => failure === 'network' ? route.abort('failed') : route.fulfill({ status: 503, json: { error: { code: 'database_busy', message: 'Database busy.' } } }))
    await batch(page).getByRole('button', { name: 'Issue certificates', exact: true }).click()
    await batch(page).getByText('Result not yet confirmed.', { exact: false }).waitFor()
    const original = keys.at(-1)
    assert.equal(await batch(page).getByRole('button', { name: 'Start a new batch', exact: true }).count(), 0)
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), storageKey), original)
    await page.unroute('**/issue-certificates')
    await batch(page).getByRole('button', { name: 'Retry original batch' }).click()
    await batch(page).getByText('No enrollments in this course.', { exact: true }).waitFor()
    assert.equal(keys.at(-1), original)
    await batch(page).getByRole('button', { name: 'Start a new batch', exact: true }).click()
  }
  await closeBatch(page)
  console.log('PASS real idempotency conflict: cancel preserves key, confirmed new batch uses a new key; network/503 retain original-key retry')

  // Simulate a course cached before its end; the real server already considers it ended.
  // Delay refresh so the test can verify stale eligibility cannot enable submission.
  let releaseCourses
  const coursesGate = new Promise(resolve => { releaseCourses = resolve })
  await page.route('**/api/courses', async route => {
    await coursesGate; await route.continue()
  })
  const refreshing = page.waitForRequest(request => request.url().endsWith('/api/courses'))
  await page.getByRole('button', { name: 'Issue certificates', exact: true }).first().click()
  await refreshing
  assert.equal(await batch(page).getByRole('button', { name: 'Issue certificates', exact: true }).isDisabled(), true)
  releaseCourses()
  await batch(page).getByText('Refreshing course eligibility…', { exact: true }).waitFor({ state: 'hidden' })
  await batch(page).locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: 'Empty Course', exact: true }).click()
  await page.unroute('**/api/courses')
  await closeBatch(page)
  await page.route('**/api/courses', async route => {
    const response = await route.fetch(); const body = await response.json()
    for (const course of body.items) if (course.id === empty.id) { course.is_finished = false; course.ends_at = new Date(Date.now() + 1000).toISOString() }
    await route.fulfill({ json: body })
  })
  await openBatch(page)
  assert.equal(await batch(page).getByRole('button', { name: 'Issue certificates', exact: true }).isDisabled(), true)
  await closeBatch(page)
  await page.unroute('**/api/courses')
  await openBatch(page)
  assert.equal(await batch(page).getByText('This course has not finished.', { exact: false }).count(), 0)
  assert.equal(await batch(page).getByRole('button', { name: 'Issue certificates', exact: true }).isEnabled(), true)
  await page.route('**/api/courses', route => route.fulfill({ status: 503, json: { error: { code: 'database_busy', message: 'Database busy.' } } }))
  await batch(page).getByRole('button', { name: 'Refresh courses', exact: true }).click()
  await batch(page).getByText('Courses could not be loaded:', { exact: false }).waitFor()
  assert.equal(await batch(page).getByRole('button', { name: 'Issue certificates', exact: true }).isDisabled(), true)
  await page.unroute('**/api/courses')
  await batch(page).getByRole('button', { name: 'Retry courses', exact: true }).click()
  await batch(page).getByRole('button', { name: 'Issue certificates', exact: true }).click()
  await batch(page).getByText('No enrollments in this course.', { exact: true }).waitFor()
  await screenshot(page, 'courses-refreshed')
  await closeBatch(page)
  assert.equal(await page.locator('vite-error-overlay').count(), 0)
  assert.deepEqual(errors, [])
  await context.close()
  console.log('PASS course refresh on open, stale unfinished state, loading/error submission guard and explicit retry; no runtime errors')
} finally { await browser.close() }
