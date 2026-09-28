import { ElMessage } from 'element-plus'

/** 业务写入完成后，刷新失败不能再提示“保存失败”或重新提交写入。 */
export async function refreshAfterSave(refresh) {
  try {
    await refresh()
    return true
  } catch {
    ElMessage.warning('保存已成功，但页面数据刷新失败，请刷新列表查看最新结果，不要重复新增')
    return false
  }
}
