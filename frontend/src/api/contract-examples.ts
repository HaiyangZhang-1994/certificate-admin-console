// Shared examples for isolated UI development. Not loaded by the application.
// Only literal unions need narrowing after JSON import; use checked assignments, never casts.
import source from '../../../docs/api/examples.json'
import type {
  BulkIssueResult, CertificateDetail, CertificatePage, CourseList, Identity,
} from '@certificate-admin/api-contract'

export const identity: Identity = source.identity
export const perthIdentity: Identity = source.perth_identity
export const courses: CourseList = source.courses
export const certificatePage: CertificatePage = {
  ...source.certificate_page,
  items: source.certificate_page.items.map((item) => ({ ...item, status: 'valid' })),
}
export const certificateDetail: CertificateDetail = {
  ...source.certificate_detail, status: 'valid',
}
export const revokedCertificateDetail: CertificateDetail = {
  ...source.revoked_certificate_detail, status: 'revoked',
}
// Backend validates the JSON fixture; UI mocks can derive discriminated variants from these types.
export type BulkIssueExample = BulkIssueResult
