<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import BulkIssue from './components/BulkIssue.vue'
import { useConsole } from './useConsole'
import { api } from './api/client'
import { checked, exportUrl, formatDate } from './model'

const { identity, restoring, authBusy, authError, courses, courseError, page, loading, listError, search, query,
  detailOpen, detail, detailLoading, detailError, bulkOpen, sessionVersion, filtered,
  handle, login, logout, loadCourses, loadList, loadDetail } = useConsole()
const credentials = reactive({ username: '', password: '' })
const revokeBusy = ref(false)
const revokeError = ref('')
const bulk = ref<InstanceType<typeof BulkIssue> | null>(null)
const mock = import.meta.env.DEV && import.meta.env.VITE_API_MODE === 'mock'
const scenario = ref('normal')
const date = (value: string) => formatDate(value, identity.value?.tenant.timezone ?? 'UTC')
const canExport = computed(() => !loading.value && !listError.value && !!page.value)
async function signIn() {
  if (!credentials.username.trim() || !credentials.password) return
  await login({ username: credentials.username.trim(), password: credentials.password })
  credentials.password = ''
}
function sort({ prop, order }: { prop: string | null; order: string | null }) {
  query.sort_by = prop === 'learner_name' || prop === 'serial_number' ? prop : 'issued_at'
  query.sort_order = order === 'ascending' ? 'asc' : 'desc'
}
function clearFilters() { search.value = ''; query.q = undefined; query.course_id = undefined; query.status = undefined; query.page = 1; void loadList() }
function exportCsv() {
  if (!canExport.value) return
  const link = document.createElement('a')
  link.href = exportUrl({ ...query, q: search.value.trim() || undefined }); link.download = 'certificates.csv'
  document.body.append(link); link.click(); link.remove()
  ElMessage.info('Download requested for all matching records. Check your browser’s downloads for the result.')
}
async function revoke() {
  if (!detail.value || detail.value.status === 'revoked' || revokeBusy.value) return
  const target = detail.value; const session = sessionVersion.value
  revokeBusy.value = true; revokeError.value = ''
  try {
    await ElMessageBox.confirm(`Revoke the certificate for ${target.learner.name}? This certificate cannot be reissued through bulk issuance.`, 'Revoke certificate', { type: 'warning', confirmButtonText: 'Revoke certificate', cancelButtonText: 'Keep certificate' })
    if (session !== sessionVersion.value) return
    const updated = await checked(api.POST('/api/certificates/{id}/revoke', { params: { path: { id: target.id } } }))
    if (session !== sessionVersion.value) return
    if (detailOpen.value && detail.value?.id === target.id) detail.value = updated
    ElMessage.success('Certificate revoked.'); void Promise.all([loadList(), loadCourses()])
  } catch (error) { if (error !== 'cancel' && error !== 'close' && session === sessionVersion.value) revokeError.value = handle(error) }
  finally { revokeBusy.value = false }
}
function closeBulk(done: () => void) { if (!bulk.value?.busy) done() }
function setScenario() { document.cookie = `dev_scenario=${scenario.value}; Path=/; SameSite=Lax`; void Promise.all([loadCourses(), loadList()]) }
</script>

<template>
  <div v-if="restoring" class="initial-state" role="status"><el-skeleton :rows="5" animated /><p>Restoring your session…</p></div>
  <main v-else-if="!identity" class="login-shell">
    <section class="login-panel">
      <div class="wordmark">Certificate Admin</div><h1>Sign in</h1><p class="muted">Access your organisation’s certificate workspace.</p>
      <el-alert v-if="authError" :title="authError" type="error" :closable="false" show-icon />
      <form @submit.prevent="signIn">
        <label class="field-label" for="username">Username</label><el-input id="username" v-model="credentials.username" autocomplete="username" :disabled="authBusy" required />
        <label class="field-label" for="password">Password</label><el-input id="password" v-model="credentials.password" type="password" show-password autocomplete="current-password" :disabled="authBusy" required />
        <el-button type="primary" native-type="submit" :loading="authBusy" :disabled="!credentials.username.trim() || !credentials.password" class="login-submit">Sign in</el-button>
      </form>
      <p class="login-note">Your account determines the organisation you can access.</p>
      <el-alert v-if="mock" title="Development mock mode" description="Demo accounts: sydney.admin / perth.admin · Password: DemoPass123!" type="warning" :closable="false" />
    </section>
  </main>
  <template v-else>
    <header class="app-header"><span class="wordmark">Certificate Admin</span><div class="identity"><strong>{{ identity.tenant.name }}</strong><span>{{ identity.admin.name }}</span><el-button :loading="authBusy" @click="logout">Sign out</el-button></div></header>
    <main class="workspace">
      <div v-if="mock" class="dev-bar"><strong>Development mock · no real certificates</strong><label for="scenario">Scenario</label><select id="scenario" v-model="scenario" @change="setScenario"><option value="normal">Normal</option><option value="empty">Empty tenant</option><option value="error">List error</option><option value="partial">Partial batch failure</option><option value="uncertain">Lost batch response</option><option value="busy">503 database busy</option><option value="expired">Session expired</option><option value="conflict">409 conflict</option></select></div>
      <div class="page-heading"><div><h1>Certificates</h1><p>Manage issued certificates for your organisation.</p></div><div class="heading-actions"><el-button :disabled="!canExport" @click="exportCsv">Export CSV</el-button><el-button type="primary" :disabled="!!courseError" @click="bulkOpen = true">Issue certificates</el-button></div></div>
      <el-alert v-if="authError" :title="authError" type="error" :closable="false" />
      <div v-if="courseError" class="error-box" role="alert">Courses could not be loaded: {{ courseError }} <el-button @click="loadCourses">Retry courses</el-button></div>
      <section aria-label="Certificate list">
        <div class="filters"><el-input v-model="search" placeholder="Search learner or certificate" aria-label="Search learner or certificate" clearable :maxlength="200" /><el-select v-model="query.course_id" placeholder="All courses" aria-label="Filter by course" clearable :disabled="!!courseError"><el-option v-for="course in courses" :key="course.id" :value="course.id" :label="course.title" /></el-select><el-select v-model="query.status" placeholder="All statuses" aria-label="Filter by status" clearable><el-option label="Valid" value="valid" /><el-option label="Revoked" value="revoked" /></el-select><el-button v-if="filtered || search" @click="clearFilters">Clear filters</el-button></div>
        <div class="table-panel" :aria-busy="loading">
          <div v-if="loading" class="table-state" role="status"><el-skeleton :rows="7" animated /><p>Loading certificates…</p></div>
          <div v-else-if="listError" class="table-state" role="alert"><h2>Certificates could not be loaded</h2><p>{{ listError }}</p><el-button type="primary" @click="loadList">Retry</el-button></div>
          <template v-else-if="page">
            <el-table v-if="page.items.length" :data="page.items" row-key="id" max-height="520" :default-sort="{ prop: query.sort_by ?? 'issued_at', order: query.sort_order === 'asc' ? 'ascending' : 'descending' }" @sort-change="sort">
              <el-table-column prop="learner_name" label="Learner" min-width="190" sortable="custom"><template #default="{ row }"><strong>{{ row.learner.name }}</strong><small>{{ row.learner.email }}</small></template></el-table-column>
              <el-table-column label="Course" min-width="165"><template #default="{ row }">{{ row.course.title }}</template></el-table-column>
              <el-table-column prop="serial_number" label="Certificate number" min-width="270" sortable="custom"><template #default="{ row }"><span class="serial">{{ row.serial_number }}</span></template></el-table-column>
              <el-table-column prop="issued_at" label="Issued at" min-width="185" sortable="custom"><template #default="{ row }">{{ date(row.issued_at) }}</template></el-table-column>
              <el-table-column label="Status" width="110"><template #default="{ row }"><el-tag :type="row.status === 'valid' ? 'success' : 'danger'" effect="light">{{ row.status === 'valid' ? 'Valid' : 'Revoked' }}</el-tag></template></el-table-column>
              <el-table-column label="Action" width="85" fixed="right"><template #default="{ row }"><el-button link type="primary" :aria-label="`View certificate for ${row.learner.name}`" @click="revokeError = ''; loadDetail(row.id)">View</el-button></template></el-table-column>
            </el-table>
            <div v-else class="table-state"><el-empty :description="filtered ? 'No matching certificates' : page.total ? 'No certificates on this page' : 'No certificates yet'"><p class="muted">{{ filtered ? 'Try a different search or clear your filters.' : page.total ? 'Return to the first page to see available records.' : 'Issue certificates to eligible learners to get started.' }}</p><el-button v-if="filtered" @click="clearFilters">Clear filters</el-button><el-button v-else-if="page.total" @click="query.page = 1">First page</el-button><el-button v-else type="primary" :disabled="!!courseError" @click="bulkOpen = true">Issue certificates</el-button></el-empty></div>
            <footer class="table-footer"><span>Total {{ page.total }} certificates</span><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :page-sizes="[10, 20, 50, 100]" :total="page.total" layout="sizes, prev, pager, next" background /></footer>
          </template>
        </div>
      </section>
      <p class="timezone-note">All dates displayed in tenant timezone: <strong>{{ identity.tenant.timezone }}</strong></p>
    </main>
    <el-drawer v-model="detailOpen" title="Certificate details" size="min(540px, 100%)" :close-on-click-modal="!revokeBusy" :before-close="done => { if (!revokeBusy) done() }">
      <div v-if="detailLoading" role="status"><el-skeleton :rows="8" animated /><p>Loading certificate…</p></div>
      <div v-else-if="detailError" role="alert"><el-alert :title="detailError" type="error" :closable="false" /><el-button @click="loadDetail()">Retry details</el-button></div>
      <template v-else-if="detail"><el-tag :type="detail.status === 'valid' ? 'success' : 'danger'">{{ detail.status === 'valid' ? 'Valid' : 'Revoked' }}</el-tag><h2>{{ detail.learner.name }}</h2><p class="muted">{{ detail.learner.email }}</p><dl class="details"><dt>Course</dt><dd>{{ detail.course.title }}</dd><dt>Certificate number</dt><dd class="serial">{{ detail.serial_number }}</dd><dt>Issued at · {{ identity.tenant.timezone }}</dt><dd>{{ date(detail.issued_at) }}</dd><dt>Issued by</dt><dd>{{ detail.issued_by.name }}</dd><template v-if="detail.revoked_at"><dt>Revoked at · {{ identity.tenant.timezone }}</dt><dd>{{ date(detail.revoked_at) }}</dd><dt>Revoked by</dt><dd>{{ detail.revoked_by?.name }}</dd></template></dl><el-alert v-if="revokeError" :title="revokeError" type="error" :closable="false" /><el-button v-if="detail.status === 'valid'" type="danger" plain :loading="revokeBusy" @click="revoke">Revoke certificate</el-button><el-alert v-else title="This certificate has been revoked and will not be reissued by bulk issuance." type="info" :closable="false" /></template>
    </el-drawer>
    <el-dialog v-model="bulkOpen" title="Issue certificates" width="min(760px, calc(100% - 24px))" :before-close="closeBulk" :close-on-click-modal="false" destroy-on-close><BulkIssue v-if="bulkOpen" ref="bulk" :key="identity.admin.id" :identity="identity" :courses="courses" @refreshed="loadList(); loadCourses()" @unauthorized="handle" /></el-dialog>
  </template>
</template>
