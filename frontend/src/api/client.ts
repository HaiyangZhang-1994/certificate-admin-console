import createClient from 'openapi-fetch'
import type { paths } from '@certificate-admin/api-contract'

// Paths already include /api. Never add a second /api prefix or a tenant_id header.
export const api = createClient<paths>({
  baseUrl: '',
  credentials: 'include',
})
