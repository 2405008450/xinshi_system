// 需求状态展示与操作能力由主列表和关联详情共用。
export const demandStatusLabels = { draft: '草稿准备中', confirmed: '需求确认', paused: '需求已暂停', cancelled: '需求取消' }
export const demandStatusText = value => ({ draft: '草稿准备中', confirmed: '需求已发送', paused: '需求已暂停', cancelled: '需求已取消' }[value] || '-')
export const demandStatusType = value => ({ draft: 'info', confirmed: 'success', paused: 'warning', cancelled: 'danger' }[value] || 'info')
export const canPauseDemand = row => Boolean(row?.id && row.demandStatus === 'confirmed' && !['draft', 'fulfilled', 'cancelled'].includes(row.requestStatus) && row.progressPercent < 100)
export const canSendDemand = row => ['draft', 'cancelled'].includes(row?.demandStatus)
