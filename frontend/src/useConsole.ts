import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { CertificateDetail, CertificatePage, CertificateQuery, Course, Identity, LoginRequest } from '@certificate-admin/api-contract'
import { api } from './api/client'
import { checked, errorMessage, RequestError } from './model'

export function useConsole() {
  const identity = ref<Identity | null>(null)
  const restoring = ref(true)
  const authBusy = ref(false)
  const authError = ref('')
  const courses = ref<Course[]>([])
  const courseError = ref('')
  const page = ref<CertificatePage | null>(null)
  const loading = ref(false)
  const listError = ref('')
  const search = ref('')
  const query = reactive<CertificateQuery>({ page: 1, page_size: 20, sort_by: 'issued_at', sort_order: 'desc' })
  const detailOpen = ref(false)
  const detail = ref<CertificateDetail | null>(null)
  const detailId = ref('')
  const detailLoading = ref(false)
  const detailError = ref('')
  const bulkOpen = ref(false)
  const sessionVersion = ref(0)
  let listVersion = 0
  let detailVersion = 0
  let courseVersion = 0
  let debounce: ReturnType<typeof setTimeout> | undefined
  const filtered = computed(() => !!(query.q || query.course_id || query.status))
  function reset() {
    sessionVersion.value++
    listVersion++; detailVersion++; courseVersion++
    clearTimeout(debounce)
    identity.value = null; courses.value = []; page.value = null
    detail.value = null; detailId.value = ''; detailOpen.value = false; bulkOpen.value = false
    loading.value = false; detailLoading.value = false; listError.value = ''; courseError.value = ''; detailError.value = ''
    search.value = ''; query.q = undefined; query.course_id = undefined; query.status = undefined
    query.page = 1; query.page_size = 20; query.sort_by = 'issued_at'; query.sort_order = 'desc'
  }
  function handle(error: unknown) {
    if (error instanceof RequestError && error.status === 401 && error.code !== 'invalid_credentials') {
      reset(); authError.value = 'Your session has expired. Please sign in again.'
    }
    return errorMessage(error)
  }
  async function loadCourses() {
    const session = sessionVersion.value; const version = ++courseVersion
    courseError.value = ''
    try {
      const data = await checked(api.GET('/api/courses'))
      if (session === sessionVersion.value && version === courseVersion) courses.value = data.items
    } catch (error) { if (session === sessionVersion.value && version === courseVersion) courseError.value = handle(error) }
  }
  async function loadList() {
    if (!identity.value) return
    const version = ++listVersion; const session = sessionVersion.value
    loading.value = true; listError.value = ''; page.value = null
    try {
      const data = await checked(api.GET('/api/certificates', { params: { query: { ...query } } }))
      if (version === listVersion && session === sessionVersion.value) page.value = data
    } catch (error) { if (version === listVersion && session === sessionVersion.value) listError.value = handle(error) }
    finally { if (version === listVersion) loading.value = false }
  }
  async function loadDetail(id = detailId.value) {
    detailId.value = id; detailOpen.value = true; detail.value = null
    const version = ++detailVersion; const session = sessionVersion.value
    detailLoading.value = true; detailError.value = ''
    try {
      const data = await checked(api.GET('/api/certificates/{id}', { params: { path: { id } } }))
      if (version === detailVersion && session === sessionVersion.value && detailOpen.value) detail.value = data
    } catch (error) { if (version === detailVersion && session === sessionVersion.value) detailError.value = handle(error) }
    finally { if (version === detailVersion) detailLoading.value = false }
  }
  async function login(credentials: LoginRequest) {
    if (authBusy.value) return
    authBusy.value = true; authError.value = ''
    try {
      const user = await checked(api.POST('/api/auth/login', { body: credentials }))
      reset(); identity.value = user
      await Promise.all([loadCourses(), loadList()])
    } catch (error) { authError.value = handle(error) }
    finally { authBusy.value = false }
  }
  async function logout() {
    if (authBusy.value) return
    authBusy.value = true; authError.value = ''
    try {
      const { response, error } = await api.POST('/api/auth/logout')
      if (!response.ok) throw new RequestError(error?.error.message ?? 'Unable to sign out.', response.status)
      reset()
    } catch (error) { authError.value = handle(error) }
    finally { authBusy.value = false }
  }
  watch(search, () => {
    clearTimeout(debounce)
    // Immediately invalidate old responses while waiting for the new search.
    listVersion++; page.value = null; loading.value = !!identity.value
    debounce = setTimeout(() => { query.q = search.value.trim() || undefined; query.page = 1; void loadList() }, 300)
  })
  watch(() => [query.course_id, query.status, query.sort_by, query.sort_order, query.page_size], () => {
    query.page = 1; void loadList()
  })
  watch(() => query.page, () => { void loadList() })
  watch(detailOpen, (open) => { if (!open) { detailVersion++; detail.value = null; detailLoading.value = false } })
  onMounted(async () => {
    try { identity.value = await checked(api.GET('/api/me')); await Promise.all([loadCourses(), loadList()]) }
    catch (error) { if (!(error instanceof RequestError && error.status === 401)) authError.value = errorMessage(error) }
    finally { restoring.value = false }
  })
  return { identity, restoring, authBusy, authError, courses, courseError, page, loading, listError, search, query,
    detailOpen, detail, detailLoading, detailError, bulkOpen, sessionVersion, filtered,
    handle, login, logout, loadCourses, loadList, loadDetail }
}
