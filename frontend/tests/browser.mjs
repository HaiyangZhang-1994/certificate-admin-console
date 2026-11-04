// Run against an explicitly enabled development mock server.
// PLAYWRIGHT_MODULE optionally points to an existing Playwright index.mjs (no dependency installation needed).
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright')
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE } : {}) })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
const page = await context.newPage()
page.setDefaultTimeout(10000)
const runtimeErrors = []
page.on('pageerror', error => runtimeErrors.push(error.message))
page.on('console', message => { if (message.type() === 'warning' || (message.type() === 'error' && !message.text().includes('Failed to load resource:') && !message.text().includes('net::ERR_'))) runtimeErrors.push(message.text()) })
const requests = []
page.on('request', request => { if (request.url().includes('/api/')) requests.push({ url: request.url(), method: request.method(), key: request.headers()['idempotency-key'] }) })
const visible = text => page.getByText(text, { exact: false }).first().waitFor()
const search = page.getByRole('textbox', { name: 'Search learner or certificate' })
async function login(username = 'sydney.admin') {
  await page.getByLabel('Username', { exact: true }).fill(username)
  await page.getByLabel('Password', { exact: true }).fill('DemoPass123!')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await visible(username === 'sydney.admin' ? 'Sydney Training' : 'Perth Training')
  await page.locator('.table-footer').waitFor()
}
async function scenario(value) { await page.locator('#scenario').selectOption(value) }
async function selectCourse(title) {
  await page.getByRole('dialog', { name: 'Issue certificates' }).locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: title, exact: true }).click()
}
async function openBatch() {
  await page.getByRole('button', { name: 'Issue certificates', exact: true }).first().click()
  await page.getByRole('dialog', { name: 'Issue certificates' }).waitFor()
}
async function closeBatch() {
  const dialog = page.getByRole('dialog', { name: 'Issue certificates' })
  await dialog.getByRole('button', { name: 'Close this dialog' }).click()
  await dialog.waitFor({ state: 'hidden' })
}
async function shot(name) {
  if (!process.env.SCREENSHOT_DIR) return
  await mkdir(process.env.SCREENSHOT_DIR, { recursive: true })
  await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `${name}.png`), fullPage: false })
}
try {
  const reset = await context.request.post(`${process.env.FRONTEND_URL ?? 'http://127.0.0.1:5173'}/__dev/reset`)
  assert.equal(reset.status(), 204, 'Browser tests require an explicitly enabled mock server')
  await page.goto(process.env.FRONTEND_URL ?? 'http://127.0.0.1:5173/')
  assert.match(await page.title(), /Certificate Admin/)
  await visible('Development mock mode')
  await page.getByLabel('Username', { exact: true }).fill('sydney.admin')
  await page.getByLabel('Password', { exact: true }).fill('wrong')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await visible('Invalid username or password.')
  await login()
  await page.reload(); await visible('Total 27 certificates')
  console.log('PASS login, invalid credentials, cookie identity restoration, nonblank page')
  await page.locator('.el-pager .number').filter({ hasText: /^2$/ }).click()
  await page.waitForResponse(response => response.url().includes('/api/certificates?') && new URL(response.url()).searchParams.get('page') === '2')
  await search.fill('Alex')
  await visible('Total 1 certificates'); assert.equal(await page.locator('.el-pager .is-active').innerText(), '1')
  await page.getByRole('columnheader', { name: 'Learner' }).click()
  await visible('Total 1 certificates')
  await page.locator('.filters .el-select__wrapper').nth(1).click(); await page.getByRole('option', { name: 'Revoked', exact: true }).click()
  await visible('No matching certificates')
  await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click(); await visible('Total 27 certificates')
  console.log('PASS search, sorting, filtering, pagination reset, no-match empty state')
  await page.route('**/api/certificates?**', async route => {
    if (new URL(route.request().url()).searchParams.get('q') !== 'slow') return route.continue()
    await new Promise(resolve => setTimeout(resolve, 1600))
    await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } })
  })
  const slowRequest = page.waitForRequest(request => new URL(request.url()).searchParams.get('q') === 'slow')
  await search.fill('slow'); await slowRequest
  await search.fill('Alex'); await visible('Total 1 certificates')
  await page.waitForTimeout(1700); await visible('Total 1 certificates')
  await page.unroute('**/api/certificates?**')
  await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click(); await visible('Total 27 certificates')
  console.log('PASS stale search response cannot overwrite a newer result')
  await scenario('error'); await visible('Certificates could not be loaded')
  await page.getByRole('button', { name: 'Retry', exact: true }).click(); await visible('Certificates could not be loaded')
  await scenario('empty'); await visible('No certificates yet'); await shot('empty')
  await scenario('normal'); await visible('Total 27 certificates')
  await search.fill('Alex'); await visible('Total 1 certificates')
  await page.getByRole('button', { name: 'View certificate for Alex Chen' }).click()
  const drawer = page.getByRole('dialog', { name: 'Certificate details' })
  await drawer.getByText('21 Oct 2026, 10:30', { exact: true }).waitFor()
  await drawer.getByRole('button', { name: 'Revoke certificate', exact: true }).click()
  await page.getByRole('button', { name: 'Keep certificate' }).click()
  assert.equal(await drawer.getByRole('button', { name: 'Revoke certificate', exact: true }).count(), 1)
  await drawer.getByRole('button', { name: 'Revoke certificate', exact: true }).click()
  await page.getByRole('dialog', { name: 'Revoke certificate' }).getByRole('button', { name: 'Revoke certificate', exact: true }).click()
  await drawer.getByText('This certificate has been revoked', { exact: false }).waitFor()
  await shot('detail')
  await drawer.getByRole('button', { name: 'Close this dialog' }).click()
  await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click(); await visible('Total 27 certificates')
  console.log('PASS list error/retry, tenant empty, detail tenant timezone, revoke cancel/confirm')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  const download = await downloadPromise
  const text = await readFile(await download.path(), 'utf8')
  assert.equal(text.split('\r\n').length, 28)
  assert.equal(new URL(download.url()).searchParams.has('page'), false)
  console.log('PASS direct CSV download includes all 27 records beyond current page')
  await scenario('partial'); await page.locator('.table-footer').waitFor()
  await openBatch()
  assert.equal(await page.getByRole('dialog', { name: 'Issue certificates' }).getByRole('button', { name: 'Issue certificates', exact: true }).isDisabled(), true)
  await selectCourse('Leadership Essentials'); await visible('This course has not finished')
  assert.equal(await page.getByRole('dialog', { name: 'Issue certificates' }).getByRole('button', { name: 'Issue certificates', exact: true }).isDisabled(), true)
  await selectCourse('Workplace Safety')
  const submit = page.getByRole('dialog', { name: 'Issue certificates' }).getByRole('button', { name: 'Issue certificates', exact: true })
  const before = requests.filter(item => item.key).length
  await submit.click(); await visible('Processing course enrollments')
  assert.equal(await page.getByRole('dialog', { name: 'Issue certificates' }).locator('.dialog-actions button').isDisabled(), true)
  await visible('Batch completed with failures'); await visible('Invalid enrollment')
  assert.equal(requests.filter(item => item.key).length - before, 1)
  await shot('batch'); await closeBatch()
  console.log('PASS unfinished course blocked, in-flight disable, partial batch results')
  await scenario('uncertain'); await page.locator('.table-footer').waitFor()
  await openBatch(); await selectCourse('Workplace Safety')
  await page.getByRole('dialog', { name: 'Issue certificates' }).getByRole('button', { name: 'Issue certificates', exact: true }).click()
  await visible('Result not yet confirmed')
  const lostKey = requests.filter(item => item.key).at(-1).key
  assert.ok(await page.evaluate(key => Object.values(sessionStorage).includes(key), lostKey))
  await closeBatch(); await page.reload(); await page.locator('.table-footer').waitFor(); await openBatch(); await selectCourse('Workplace Safety')
  await visible('A previous batch is awaiting confirmation')
  await page.getByRole('button', { name: 'Retry original batch' }).click()
  await visible('Batch completed')
  assert.equal(requests.filter(item => item.key).at(-1).key, lostKey)
  assert.equal(await page.evaluate(key => Object.values(sessionStorage).includes(key), lostKey), false)
  await closeBatch()
  console.log('PASS lost response, persisted pending key across reload, original-key replay')
  await scenario('busy'); await page.locator('.table-footer').waitFor(); await openBatch(); await selectCourse('Empty Course')
  await page.getByRole('dialog', { name: 'Issue certificates' }).getByRole('button', { name: 'Issue certificates', exact: true }).click(); await visible('Result not yet confirmed')
  const busyKey = requests.filter(item => item.key).at(-1).key
  await closeBatch(); await scenario('normal'); await page.locator('.table-footer').waitFor(); await openBatch(); await selectCourse('Empty Course')
  await page.getByRole('button', { name: 'Retry original batch' }).click(); await visible('No enrollments in this course.')
  assert.equal(requests.filter(item => item.key).at(-1).key, busyKey); await closeBatch()
  console.log('PASS 503 original-key retry and zero-enrollment result')
  await scenario('conflict'); await page.locator('.table-footer').waitFor(); await openBatch(); await selectCourse('Empty Course')
  await page.getByRole('dialog', { name: 'Issue certificates' }).getByRole('button', { name: 'Issue certificates', exact: true }).click()
  await visible('This key belongs to a different request'); await closeBatch()
  await scenario('normal'); await page.locator('.table-footer').waitFor()
  await search.fill('Alex'); await visible('Total 1 certificates'); await page.getByRole('button', { name: 'View certificate for Alex Chen' }).click(); await drawer.getByText('Alex Chen', { exact: true }).waitFor(); await drawer.getByRole('button', { name: 'Close this dialog' }).click()
  let finishOldDetail
  const oldDetailFinished = new Promise(resolve => { finishOldDetail = resolve })
  await page.route('**/api/certificates/*', async route => {
    const response = await route.fetch()
    await new Promise(resolve => setTimeout(resolve, 3000))
    await route.fulfill({ response })
    finishOldDetail()
  })
  const oldDetailRequest = page.waitForRequest(request => /\/api\/certificates\/[^/?]+$/.test(request.url()))
  await page.getByRole('button', { name: 'View certificate for Alex Chen' }).click(); await oldDetailRequest
  await drawer.getByRole('button', { name: 'Close this dialog' }).click()
  await page.getByRole('button', { name: 'Sign out' }).click(); await login('perth.admin')
  await oldDetailFinished
  await page.unroute('**/api/certificates/*')
  assert.equal(await search.inputValue(), '')
  assert.equal(await page.getByRole('dialog').count(), 0)
  await visible('Total 4 certificates'); await visible('Australia/Perth')
  await openBatch(); await selectCourse('Empty Course')
  assert.equal(await page.getByText('A previous batch is awaiting confirmation', { exact: true }).count(), 0)
  await closeBatch()
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await shot('mobile')
  await page.setViewportSize({ width: 1440, height: 1000 }); await shot('desktop')
  await scenario('expired'); await visible('Your session has expired. Please sign in again.')
  assert.equal(await page.getByText('Perth Training', { exact: true }).count(), 0)
  console.log('PASS 409 reason, account state reset, narrow screen, 401 private-state cleanup')
  assert.deepEqual(runtimeErrors, [])
  assert.equal(await page.locator('vite-error-overlay').count(), 0)
  console.log('PASS no framework overlay, runtime errors or Vue warnings')
} catch (error) {
  await shot('failure')
  console.error(await page.locator('body').innerText())
  throw error
} finally { await browser.close() }


