<template>
  <div class="referral-detail-content">
    <el-descriptions :column="2" border size="small">
      <el-descriptions-item v-for="field in referralColumns" :key="field.key" :label="field.label" :span="['pull_description','moments_description','groups_description','remarks'].includes(field.key) ? 2 : 1">{{ displayReferralValue(record, field.key) }}</el-descriptions-item>
    </el-descriptions>
    <el-alert v-if="record.contact_restricted" title="微信及凭证仅向本人、管理员和有代录权限的人员展示。" type="info" :closable="false" />
    <template v-else><section v-for="category in imageCategories" :key="category.key"><h4>{{ category.label }}</h4><ReferralImages :images="record.images?.filter(i => i.category === category.key) || []" /></section></template>
    <h4>操作历史</h4>
    <section v-for="entry in record.audit || []" :key="entry.id" class="referral-audit-entry">
      <strong>{{ auditLabels[entry.action] || entry.action }}</strong><span> · {{ entry.actor_name }} · {{ timeText(entry.created_at) }}</span>
      <div v-for="change in auditChanges(entry)" :key="change.key" class="referral-audit-change">{{ change.label }}：{{ change.before }} → {{ change.after }}</div>
      <div v-if="entry.before?.images?.length" class="referral-audit-change">原图片：{{ imageNames(entry.before.images) }}</div>
      <div v-if="entry.after?.images?.length" class="referral-audit-change">新图片：{{ imageNames(entry.after.images) }}</div>
    </section>
    <p v-if="!record.audit?.length">暂无操作历史</p>
  </div>
</template>

<script setup>
import ReferralImages from './ReferralImages.vue'
import { referralColumns, displayReferralValue, imageCategories, auditLabels, auditChanges, timeText } from '@/utils/referralDevelopment'
defineProps({ record: { type: Object, required: true } })
const imageNames = images => images.map(i => `${imageCategories.find(c => c.key === i.category)?.label || ''} · ${i.name}`).join('、')
</script>

<style scoped>
.referral-detail-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto;overflow-wrap:anywhere;white-space:pre-wrap}.referral-detail-content h4{margin:16px 0 10px}.referral-detail-content section{margin-bottom:12px}.referral-audit-entry{padding:12px;background:#f8fafc;border-radius:6px;font-size:12px;line-height:1.8}.referral-audit-entry>span{color:#64748b}.referral-audit-change{color:#475569;margin-top:4px}.referral-detail-content .el-alert{margin-top:12px}
</style>
