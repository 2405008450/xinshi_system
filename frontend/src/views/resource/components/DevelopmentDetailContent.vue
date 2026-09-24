<template>
  <div class="development-detail-content">
    <header class="detail-identity">
      <div><h3>{{ record.full_name || '-' }}</h3><p>{{ record.greeting_no || '暂无招呼编号' }}</p></div>
      <el-tag v-if="record.historical_only" type="info" effect="plain" round>历史导入</el-tag>
    </header>
    <el-alert v-if="record.person_id" type="success" :closable="false" :title="`已入人才总库 · ${record.resource_code || '已关联档案'}`" />
    <section class="detail-section">
      <h4>基本资料</h4>
      <el-descriptions :column="2" border size="small" class="detail-facts">
        <el-descriptions-item v-for="field in fields" :key="field.key" :label="field.label" label-width="96px">{{ field.key === 'work_date' ? date(record[field.key]) : field.key === 'updated_at' ? time(record[field.key]) : record[field.key] || '-' }}</el-descriptions-item>
        <el-descriptions-item label="语种 / 方言" :span="2" label-width="96px">{{ record.language_names || '-' }}</el-descriptions-item>
      </el-descriptions>
    </section>
    <section class="detail-section">
      <h4>跟进进展</h4>
      <div class="detail-progress-grid"><div v-for="(label, channel) in progressChannels" :key="channel" class="detail-progress-card">
        <span class="detail-eyebrow">{{ label }}</span>
        <strong :class="{ 'is-complete': completed(channel) }">{{ record.progress?.[channel]?.status || '未处理' }}</strong>
        <small v-if="record.progress?.[channel]">{{ date(record.progress[channel].action_date) }} · {{ record.progress[channel].operator_name || '原表未填写' }}</small>
        <small v-else>暂无跟进记录</small>
      </div></div>
    </section>
    <section class="detail-section detail-notes"><h4>补充说明</h4>
      <div class="detail-note"><span class="detail-eyebrow">后续跟进</span><p>{{ record.follow_up || '-' }}</p></div>
      <div class="detail-note"><span class="detail-eyebrow">备注</span><p>{{ notes.business || '-' }}</p></div>
      <div v-for="(note, index) in notes.notices" :key="index" class="detail-note detail-notice">{{ note }}</div>
    </section>
    <section v-if="history.length" class="detail-section"><h4>跟进记录 <span>{{ history.length }} 条</span></h4>
      <ol class="detail-history"><li v-for="action in history" :key="action.id">
        <div class="detail-history-title"><strong>{{ progressChannels[action.channel] || action.channel }} · {{ action.status }}</strong><time>{{ date(action.action_date) }}</time></div>
        <p>{{ action.operator_name || '-' }}<template v-if="action.account_id"> · {{ accountName(action.account_id) }}</template><template v-if="action.request_number"> · 第 {{ action.request_number }} 次申请</template></p>
        <small>录入：{{ action.created_by_name || '-' }} · 修改：{{ action.updated_by_name || '-' }} / {{ time(action.updated_at) }}</small>
      </li></ol>
    </section>
    <el-collapse class="detail-secondary">
      <el-collapse-item v-if="notes.source || notes.raw" title="历史导入来源与原表信息" name="source">
        <p class="detail-source">{{ notes.source }}</p>
        <dl v-if="notes.original" class="detail-original"><template v-for="(value, key) in notes.original" :key="key"><dt>{{ key }}</dt><dd>{{ value === null || value === '' ? '-' : value }}</dd></template></dl>
        <p v-else class="detail-source">{{ notes.raw }}</p>
      </el-collapse-item>
      <el-collapse-item :title="`系统记录 · 最近更新 ${time(record.updated_at)}`" name="audit">
        <div v-for="entry in record.audit || []" :key="entry.id" class="detail-audit">{{ time(entry.created_at) }} · {{ entry.actor_name || '-' }} · {{ auditLabel(entry.action) }}</div>
        <p v-if="!record.audit?.length" class="detail-source">暂无可查看的修改记录</p>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { progressChannels } from '@/utils/resourceDevelopment'
const props = defineProps({ record: { type: Object, required: true }, accounts: { type: Array, default: () => [] } })
const fields = [{ key: 'platform_name', label: '开拓平台' }, { key: 'work_date', label: '业务日期' }, { key: 'owner_name', label: '开拓人员' }, { key: 'account_name', label: '对接账号' }, { key: 'phone', label: '手机号' }, { key: 'wechat', label: '微信号' }, { key: 'resource_code', label: '资源编号' }, { key: 'updated_at', label: '最近更新' }]
const date = value => value ? new Date(`${String(value).slice(0, 10)}T00:00:00`).toLocaleDateString('zh-CN') : '原表未填写'
const time = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
const accountName = id => props.accounts.find(a => a.id === id)?.name || '-'
const completed = channel => ['已添加', '已进群', '已沟通', '已入项'].includes(props.record.progress?.[channel]?.status)
const auditLabel = action => ({ create: '新增', update: '修改', delete: '删除', import_history_repair: '补齐历史导入明细' })[action] || action
const history = computed(() => [...(props.record.actions || [])].sort((a, b) => String(b.action_date).localeCompare(String(a.action_date))))
// 仅整理已知导入标记的显示；原始备注不修改，解析失败仍可查看完整原文。
const notes = computed(() => {
  const result = { business: '', source: '', raw: '', original: null, notices: [] }
  const business = []
  for (const line of (props.record.remarks || '').split('\n')) {
    if (props.record.historical_only && line.startsWith('【历史导入】')) result.source += line.slice(6)
    else if (props.record.historical_only && line.startsWith('【原表信息】')) {
      result.raw += line.slice(6)
      try { const parsed = JSON.parse(result.raw); if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) result.original = parsed } catch { /* 原文作为回退显示。 */ }
    } else if (props.record.historical_only && /^【(待核对|未映射语种原文)】/.test(line)) result.notices.push(line)
    else business.push(line)
  }
  result.business = business.join('\n').trim()
  return result
})
</script>

<style scoped>
.development-detail-content{color:var(--el-text-color-primary);font-size:13px;line-height:1.6;padding:0 4px 4px}
.detail-identity{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:4px 0 18px;border-bottom:1px solid var(--el-border-color-lighter)}
.detail-identity h3{font-size:20px;line-height:1.4;margin:0 0 6px;overflow-wrap:anywhere}.detail-identity p{margin:0;color:var(--el-text-color-secondary);font-size:12px;font-variant-numeric:tabular-nums;user-select:text}
.detail-section{margin:20px 0}.detail-section h4{margin:0 0 10px;font-size:14px;font-weight:600}.detail-section h4 span{font-size:12px;color:var(--el-text-color-secondary);font-weight:400;margin-left:6px}
.detail-facts :deep(.el-descriptions__table){table-layout:fixed;width:100%}.detail-facts :deep(.el-descriptions__label){width:96px!important;white-space:nowrap;color:#64748b;font-weight:400;background:#f8fafc!important}.detail-facts :deep(.el-descriptions__cell){padding:10px 12px!important;overflow-wrap:anywhere;vertical-align:top}.detail-facts :deep(.el-descriptions__content){white-space:pre-wrap;color:#253449}
.detail-progress-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.detail-progress-card{padding:12px;background:#f8fafc;border:1px solid #e8edf3;border-radius:8px;min-width:0}.detail-progress-card strong,.detail-progress-card small{display:block}.detail-progress-card strong{font-size:14px;margin:4px 0;color:#64748b}.detail-progress-card strong.is-complete{color:#16805d}.detail-progress-card small{font-size:12px;color:#7b8798;overflow-wrap:anywhere}.detail-eyebrow{font-size:12px;color:#64748b}
.detail-note{padding:10px 14px;background:#f8fafc;border-radius:6px;margin-top:8px;white-space:pre-wrap;overflow-wrap:anywhere}.detail-note p{margin:4px 0 0}.detail-notice{background:#fff8e8;color:#875b19;font-size:12px}
.detail-history{list-style:none;margin:0;padding:0 0 0 12px}.detail-history li{position:relative;padding:0 0 18px 18px;border-left:1px solid #dce5ef}.detail-history li:before{content:'';position:absolute;left:-4px;top:7px;width:7px;height:7px;border-radius:50%;background:#8fa6c0}.detail-history li:last-child{padding-bottom:0}.detail-history-title{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.detail-history time,.detail-history small{font-size:12px;color:#8491a3}.detail-history p{margin:4px 0;font-size:12px;color:#64748b}
.detail-secondary{--el-collapse-border-color:#edf0f4}.detail-secondary :deep(.el-collapse-item__header){font-size:12px;color:#64748b;line-height:1.5;padding:10px 0;height:auto;min-height:44px}.detail-source{white-space:pre-wrap;overflow-wrap:anywhere;color:#64748b}.detail-original{display:grid;grid-template-columns:130px minmax(0,1fr);margin:0;font-size:12px}.detail-original dt,.detail-original dd{margin:0;padding:8px 10px;border-bottom:1px solid #edf0f4;overflow-wrap:anywhere}.detail-original dt{color:#64748b;background:#f8fafc}.detail-audit{font-size:12px;color:#64748b;padding:6px 0}
@media(max-width:600px){.detail-progress-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.detail-facts :deep(.el-descriptions__label){width:76px!important;font-size:12px}.detail-facts :deep(.el-descriptions__cell){padding:8px 6px!important}.detail-original{grid-template-columns:100px minmax(0,1fr)}}
</style>
