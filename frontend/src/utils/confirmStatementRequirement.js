import { ElMessageBox } from 'element-plus'
import { h } from 'vue'
import { getStatementRequirementContext } from '@/api/translationCustomerFinance'
import { currentStatementMonth } from './statementRequirementMonth'

const defaultLabels = { required: '默认需对账单', not_required: '默认无需对账单', unknown: '未知' }

export function notifyStatementCustomerSync(scope) {
  if (scope) window.dispatchEvent(new CustomEvent('customer-statement-preference-saved', {
    detail: { clientId: scope.client_id, fromProject: true },
  }))
}

export async function confirmStatementRequirement({ projectId, clientId, billingMonth, value, allowMonthSync = true }) {
  const nextLabel = value ? '需对账单' : '无需对账单'
  const context = await getStatementRequirementContext({
    project_id: projectId || undefined,
    client_id: clientId || undefined,
    billing_month: projectId ? undefined : billingMonth || currentStatementMonth(),
  })
  const defaultLabel = context.clientId ? defaultLabels[context.statementDefault] || '未知' : '未关联客户'
  const hasPeers = allowMonthSync && context.otherCount > 0
  const message = [`客户对账单默认设置：${defaultLabel}。本次将当前项目设为「${nextLabel}」。`]
  if (hasPeers) message.push(`${context.billingMonth} 还有 ${context.otherCount} 个同客户项目，是否也同步为「${nextLabel}」？`)
  let syncCustomer = false
  const content = h('div', [
    ...message.map(line => h('p', line)),
    context.canUpdateCustomer && h('label', { style: 'display:flex;gap:8px;align-items:center;margin-top:12px' }, [
      h('input', { type: 'checkbox', onChange: event => { syncCustomer = event.target.checked } }),
      `将客户管理中的对账单默认设置更新为「${nextLabel}」（尚未人工设置的项目会继承此值）`,
    ]),
  ])
  const result = scope => ({
    scope,
    customerScope: syncCustomer ? { client_id: context.clientId, revision: context.preferenceRevision } : null,
  })
  try {
    await ElMessageBox.confirm(content, allowMonthSync ? '调整对账单需求' : '重新确认对账单需求', {
      confirmButtonText: hasPeers ? '同步同月其他项目' : allowMonthSync ? '确认调整' : '确认',
      cancelButtonText: hasPeers ? '跳过同月同步' : '取消',
      distinguishCancelAndClose: true,
      closeOnClickModal: false,
      type: 'warning',
    })
    return result(hasPeers ? { client_id: context.clientId, billing_month: context.billingMonth } : null)
  } catch (action) {
    if (hasPeers && action === 'cancel') return result(null)
    if (action === 'cancel' || action === 'close') return null
    throw action
  }
}
