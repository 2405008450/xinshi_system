export const associatedProjectTypes = Object.freeze({ annotation: '标注', translation: '笔译', interpretation: '口译', recruitment: '招聘' })

export function associatedProject(request) {
  const sourceType = request?.sourceType
  const projectId = request?.[`${sourceType}ProjectId`]
  return Object.hasOwn(associatedProjectTypes, sourceType || '') && projectId ? { sourceType, projectId: String(projectId) } : null
}

export function associatedProjectError(error) {
  const status = error?.status || error?.response?.status
  if (status === 403) return '没有权限查看该项目详情'
  if (status === 404) return '关联项目不存在或已被删除，需求中的历史信息仍保留'
  return '项目详情加载失败，请重试'
}

/** 每次打开重新读取；取消后即使旧请求返回，也不能覆盖新的目标。 */
export function createAssociatedProjectLoader(fetchDetail, publish) {
  let controller, sequence = 0
  const cancel = () => { sequence++; controller?.abort() }
  const load = async target => {
    cancel()
    const serial = sequence
    controller = new AbortController()
    const signal = controller.signal
    publish({ loading: true, detail: null, error: '', extras: {} })
    try {
      const { detail, ...extras } = await fetchDetail(target, signal)
      if (serial === sequence) publish({ loading: false, detail, error: '', extras })
    } catch (error) {
      if (serial === sequence && !signal.aborted) publish({ loading: false, detail: null, error: associatedProjectError(error), extras: {} })
    }
  }
  return { load, cancel }
}
