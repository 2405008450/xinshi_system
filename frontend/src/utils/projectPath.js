const normalizePath = (value) => String(value || '').trim()

const readPath = (source, snakeCaseKey, camelCaseKey) => (
  normalizePath(source?.[snakeCaseKey]) || normalizePath(source?.[camelCaseKey])
)

/**
 * 按业务优先级选择笔译项目当前可用的文件路径。
 * 项目文件接口使用 snake_case，项目列表使用 camelCase，因此同时兼容两种字段名。
 */
export const resolvePreferredProjectPath = (projectFile = {}, project = {}) => {
  const candidates = [
    { source: '原文路径', path: readPath(projectFile, 'storage_path', 'storagePath') },
    { source: '派稿文路径', path: readPath(projectFile, 'dispatch_path', 'dispatchPath') },
    { source: '参考文件路径一', path: readPath(project, 'reference_file_path_one', 'referenceFilePathOne') },
    { source: '译文路径', path: readPath(projectFile, 'translation_path', 'translationPath') },
    { source: '译员发回路径', path: readPath(projectFile, 'translator_return_path', 'translatorReturnPath') },
    { source: '发客户路径', path: readPath(projectFile, 'client_delivery_path', 'clientDeliveryPath') },
    { source: '项目反馈路径', path: readPath(projectFile, 'project_feedback_path', 'projectFeedbackPath') },
    { source: '反馈后发客户路径', path: readPath(projectFile, 'feedback_delivery_path', 'feedbackDeliveryPath') },
    { source: '网络文件路径', path: readPath(project, 'network_file_path', 'networkFilePath') },
  ]

  return candidates.find((candidate) => candidate.path) || null
}
