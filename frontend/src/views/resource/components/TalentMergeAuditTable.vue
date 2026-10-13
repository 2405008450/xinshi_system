<template>
  <div v-if="audit" class="merge-audit">
    <p>合并前档案：{{ audit.participants.map(member => `${member.name} · ${member.code || member.id}`).join('、') }}</p>
    <p>保留档案：{{ label(audit.target_id) }}；归档：{{ audit.archive_ids.map(label).join('、') || '无' }}</p>
    <p>{{ audit.history_policy }}</p>
    <el-alert v-for="warning in audit.warnings || []" :key="warning" :title="warning" type="warning" :closable="false" />
    <el-checkbox v-model="differencesOnly">只看变化或冲突字段</el-checkbox>
    <el-table :data="fields" border size="small" class="merge-audit-table">
      <el-table-column prop="label" label="字段" width="140" fixed />
      <el-table-column label="处理方式" min-width="200"><template #default="{ row }">{{ row.method }}<div v-if="Object.keys(row.choices || {}).length" class="audit-value">取值来源：{{ [...new Set(Object.values(row.choices).map(choice => choice.person_id ? label(choice.person_id) : '人工修正'))].join('、') }}</div></template></el-table-column>
      <el-table-column label="主档合并前" min-width="200"><template #default="{ row }"><div class="audit-value">{{ reviewDisplay(row.before_value) }}</div></template></el-table-column>
      <el-table-column label="合并后" min-width="230"><template #default="{ row }"><div class="audit-value">{{ reviewDisplay(row.value) }}</div></template></el-table-column>
      <el-table-column label="各来源原值" min-width="260"><template #default="{ row }"><div v-for="option in row.options" :key="option.person_id" class="audit-value">{{ label(option.person_id) }}：{{ reviewDisplay(option.value) }}</div></template></el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { reviewDisplay } from '@/utils/talentDuplicateReview'
const props = defineProps({ audit: { type: Object, default: null } })
const differencesOnly = ref(true)
const fields = computed(() => (props.audit?.fields || []).filter(field => !differencesOnly.value || field.changed || field.state === 'conflict'))
const label = id => { const member = props.audit?.participants.find(item => item.id === id); return member ? `${member.name} · ${member.code || id}` : id }
</script>

<style scoped>
.merge-audit p { overflow-wrap:anywhere; line-height:1.7; margin:10px 0 }.audit-value { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.6 }
</style>
