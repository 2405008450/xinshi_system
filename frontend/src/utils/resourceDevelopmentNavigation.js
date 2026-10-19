export const RESOURCE_DEVELOPMENT_PATH = '/resource-management/resource-development'

export function resourceRequestsLocation(to) {
  return {
    path: RESOURCE_DEVELOPMENT_PATH,
    query: { ...to.query, section: 'requests' },
    hash: to.hash,
  }
}

/** 页签位置与默认页签独立：有开拓权限时继续默认打开日志。 */
export function resolveDevelopmentSection(section, { canRequests, canResource, canIssues }) {
  const sections = [
    ...(canRequests ? ['requests'] : []),
    ...(canResource ? ['logs', 'arrangements'] : []),
    ...(canIssues ? ['issues'] : []),
  ]
  return sections.includes(section) ? section : canResource ? 'logs' : sections[0] || ''
}
