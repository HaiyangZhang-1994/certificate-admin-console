<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { BulkIssueResult, Course, Identity, LearnerOutcome } from '@certificate-admin/api-contract'
import { api } from '../api/client'
import { batchStorageKey, checked, errorMessage, RequestError, uncertain } from '../model'

const props = defineProps<{ identity: Identity; courses: Course[] }>()
const emit = defineEmits<{ refreshed: []; unauthorized: [error: unknown] }>()
const courseId = ref('')
const busy = ref(false)
const error = ref('')
const pending = ref('')
const result = ref<BulkIssueResult | null>(null)
let disposed = false
onBeforeUnmount(() => { disposed = true })
const rows = computed(() => result.value?.results.map(item => ({ ...item, description: reason(item) })) ?? [])
const course = computed(() => props.courses.find(item => item.id === courseId.value))
const storageError = ref('')
watch(courseId, () => {
  result.value = null; error.value = ''; storageError.value = ''
  try { pending.value = sessionStorage.getItem(batchStorageKey(props.identity, courseId.value)) ?? '' }
  catch { storageError.value = 'Session storage is unavailable. Enable it before issuing certificates.' }
})
function reason(item: LearnerOutcome) {
  if (item.outcome === 'issued') return 'Certificate issued'
  return { not_completed: 'Enrollment not completed', already_issued: 'Certificate already exists',
    certificate_revoked: 'Existing certificate was revoked', invalid_enrollment: 'Invalid enrollment — review learner data' }[item.reason]
}
async function issue() {
  if (busy.value || !course.value || (!pending.value && !course.value.is_finished) || storageError.value) return
  busy.value = true; error.value = ''; result.value = null
  const storageKey = batchStorageKey(props.identity, courseId.value)
  try {
    if (!pending.value) {
      try {
        const key = crypto.randomUUID()
        sessionStorage.setItem(storageKey, key)
        pending.value = key
      } catch {
        storageError.value = 'The retry key could not be saved. No request was sent. Enable session storage and reopen this dialog.'
        return
      }
    }
    const response = await checked(api.POST('/api/courses/{id}/issue-certificates', {
      params: { path: { id: courseId.value }, header: { 'Idempotency-Key': pending.value } },
    }))
    // openapi-fetch 0.17 Readable<T> drops null-only properties. Validate them
    // at runtime and reconstruct checked DTO variants, without casting the wire response.
    const results: BulkIssueResult['results'] = response.results.map(row => {
      if (row.outcome === 'issued') {
        if (!('reason' in row) || row.reason !== null) throw new RequestError('Invalid issuance response.', 500)
        return { ...row, reason: null }
      }
      if (row.outcome === 'failed') {
        if (!('certificate_id' in row) || row.certificate_id !== null || !('serial_number' in row) || row.serial_number !== null) throw new RequestError('Invalid issuance response.', 500)
        return { ...row, certificate_id: null, serial_number: null }
      }
      return row
    })
    sessionStorage.removeItem(storageKey)
    if (disposed) return
    result.value = { ...response, results }; pending.value = ''
    emit('refreshed')
  } catch (failure) {
    if (disposed) return
    if (uncertain(failure)) error.value = `Result not yet confirmed. ${errorMessage(failure)} Retry this batch with the original key.`
    else error.value = errorMessage(failure)
    emit('unauthorized', failure)
  } finally { busy.value = false }
}
function newBatch() { result.value = null; error.value = '' }
defineExpose({ busy })
</script>

<template>
  <p class="muted">Issue certificates to completed learners in a finished course. Existing certificates are skipped, including revoked certificates.</p>
  <label class="field-label" for="issue-course">Course</label>
  <el-select id="issue-course" v-model="courseId" placeholder="Select a course" :disabled="busy || !!result" style="width: 100%">
    <el-option v-for="item in courses" :key="item.id" :value="item.id" :label="item.title" />
  </el-select>
  <div v-if="course" class="course-summary">
    <span><strong>{{ course.enrollment_count }}</strong> enrolled</span><span><strong>{{ course.completed_count }}</strong> completed</span>
    <span><strong>{{ course.eligible_count }}</strong> eligible</span><span><strong>{{ course.already_issued_count }}</strong> already issued</span>
  </div>
  <el-alert v-if="course && !course.is_finished" title="This course has not finished. New certificates cannot be issued yet." type="warning" :closable="false" />
  <el-alert v-if="pending && !busy && !result" title="A previous batch is awaiting confirmation" description="Retry uses the saved original key. It will safely retrieve the original result if the batch already completed." type="warning" :closable="false" show-icon />
  <el-alert v-if="error || storageError" :title="error || storageError" type="error" :closable="false" show-icon />
  <div v-if="busy" class="processing" role="status" aria-live="polite"><span class="indeterminate" />Processing course enrollments. Waiting for the server’s final result…</div>
  <template v-if="result">
    <el-alert :type="result.failed_count ? 'warning' : 'success'" :title="result.failed_count ? 'Batch completed with failures — review the results below' : 'Batch completed'" :closable="false" show-icon />
    <div class="course-summary" aria-live="polite"><span><strong>{{ result.issued_count }}</strong> issued</span><span><strong>{{ result.skipped_count }}</strong> skipped</span><span><strong>{{ result.failed_count }}</strong> failed</span></div>
    <el-table :data="rows" max-height="330" empty-text="No enrollments in this course.">
      <el-table-column prop="learner_name" label="Learner" min-width="140" />
      <el-table-column label="Outcome" width="115"><template #default="{ row }"><el-tag :type="row.outcome === 'issued' ? 'success' : row.outcome === 'failed' ? 'danger' : 'info'">{{ row.outcome }}</el-tag></template></el-table-column>
      <el-table-column label="Result" min-width="240"><template #default="{ row }">{{ row.description }}<small v-if="row.serial_number" class="serial">{{ row.serial_number }}</small></template></el-table-column>
    </el-table>
    <p class="muted">Retrying a completed batch does not reprocess failed learners. Start a new batch after correcting their data.</p>
    <el-button @click="newBatch">Start a new batch</el-button>
  </template>
  <div v-else class="dialog-actions"><el-button type="primary" :loading="busy" :disabled="!course || (!course.is_finished && !pending) || !!storageError" @click="issue">{{ busy ? 'Processing…' : pending ? 'Retry original batch' : 'Issue certificates' }}</el-button></div>
</template>
