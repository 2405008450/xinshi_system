import { ref } from 'vue'
import { getResourceRequestSourceStatuses } from '@/api/resourceRequests'

const actionLabels = {
  draft: '编辑需求草稿',
  confirmed: '查看需求（已发送）',
  paused: '查看需求（已暂停）',
  cancelled: '查看需求（已取消）',
}

/**
 * 为项目列表批量加载资源需求生命周期，避免每一行单独请求。
 */
export const useResourceRequestStatuses = (sourceType) => {
  const statuses = ref({})

  const load = async () => {
    try {
      statuses.value = await getResourceRequestSourceStatuses(sourceType) || {}
    } catch {
      // 状态提示加载失败不应阻断项目主列表；点击后仍会按来源项目查找原需求。
      statuses.value = {}
    }
  }

  const actionLabel = (projectId) => actionLabels[statuses.value[projectId]] || '发起需求'

  return { statuses, load, actionLabel }
}
