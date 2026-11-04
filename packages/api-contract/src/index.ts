// Wire types only. Do not add frontend state or database models here.
import type { components, operations } from './schema'

export type { components, operations, paths } from './schema'
export type Identity = components['schemas']['Identity']
export type LoginRequest = components['schemas']['LoginRequest']
export type Course = components['schemas']['CourseSummary']
export type CourseList = components['schemas']['CourseList']
export type Certificate = components['schemas']['CertificateSummary']
export type CertificateDetail = components['schemas']['CertificateDetail']
export type CertificatePage = components['schemas']['CertificatePage']
export type BulkIssueResult = components['schemas']['BulkIssueResult']
export type LearnerOutcome = BulkIssueResult['results'][number]
export type ApiErrorResponse = components['schemas']['ErrorResponse']
export type CertificateQuery = NonNullable<operations['listCertificates']['parameters']['query']>
export type ExportQuery = NonNullable<operations['exportCertificates']['parameters']['query']>
