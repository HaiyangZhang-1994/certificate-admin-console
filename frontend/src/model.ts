import type { CertificateQuery, ExportQuery, Identity } from '@certificate-admin/api-contract'

export function exportUrl(query: CertificateQuery) {
  const { page, page_size, ...filters }: CertificateQuery = query
  const params = new URLSearchParams()
  Object.entries(filters satisfies ExportQuery).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return `/api/certificates/export.csv?${params}`
}

export function batchStorageKey(identity: Identity, course: string) {
  return `certificate-batch:v1:${identity.tenant.id}:${identity.admin.id}:${course}`
}

export function formatDate(value: string, timezone: string) {
  return new Intl.DateTimeFormat('en-AU', {
    timeZone: timezone, year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}

export class RequestError extends Error {
  constructor(message: string, public status = 0, public code = 'network_error') { super(message) }
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'An unexpected error occurred. Please retry.'
}

export function uncertain(error: unknown) {
  return !(error instanceof RequestError) || error.status === 0 || error.status >= 500
}

export async function checked<T>(request: Promise<{ data?: T; error?: { error: { code: string; message: string } }; response: Response }>): Promise<T> {
  try {
    const { data, error, response } = await request
    if (!response.ok) throw new RequestError(error?.error.message ?? `Request failed (${response.status}).`, response.status, error?.error.code)
    if (data === undefined) throw new RequestError('The server returned an empty response.', 500)
    return data
  } catch (error) {
    if (error instanceof RequestError) throw error
    throw new RequestError('Unable to reach the server. Check your connection and retry.')
  }
}
