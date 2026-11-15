<template>
  <el-empty v-if="!clientId" description="请先保存客户，再维护客户要求" />
  <el-tabs v-else v-model="active" v-loading="loading">
    <el-tab-pane v-for="(module, key) in requirementModules" :key="key" :name="key" :label="module.label" />
    <el-alert v-if="error" type="error" :title="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-card v-for="(label, field) in fields" :key="`${active}:${field}`" shadow="never" class="requirement-card">
      <template #header><strong>{{ label }}</strong></template>
      <div :data-dialog-field-search-label="label">
        <ol v-if="history[field]?.length" class="requirement-history">
          <li v-for="item in history[field]" :key="item.id">
            <div class="requirement-content">{{ item.content }}</div>
            <small>增加日期 {{ formatDate(item.added_at) }}<template v-if="item.source_order_no"> · 来源订单 {{ item.source_order_no }}</template></small>
          </li>
        </ol>
        <p v-else>暂无记录</p>
        <el-input v-if="canWrite" v-model="draft[field]" type="textarea" :rows="2" :disabled="saving"
          maxlength="10000" :aria-label="`新增${label}`" placeholder="填写后新增一条记录" />
        <el-button v-if="canWrite" :disabled="loading || !!error || saving || !draft[field]?.trim()" @click="append(field)">新增记录</el-button>
      </div>
    </el-card>
  </el-tabs>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { requirementModules, requirementPath } from '@/utils/customerRequirements'

const props = defineProps({ clientId: String, canWrite: Boolean })
const active = ref('translation')
const fields = computed(() => requirementModules[active.value].fields)
const history = ref({})
const draft = ref({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const dateFormat = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Hong_Kong', dateStyle: 'medium', timeStyle: 'medium' })
const formatDate = value => dateFormat.format(new Date(value))
let requestId = 0

async function load() {
  const id = ++requestId
  history.value = {}
  error.value = ''
  loading.value = Boolean(props.clientId)
  if (!props.clientId) return
  try {
    const { items } = await api.get(requirementPath(props.clientId, active.value))
    if (id !== requestId) return
    for (const item of [...items].reverse()) (history.value[item.field] ??= []).push(item)
  } catch (e) {
    if (id === requestId) error.value = getLocalizedErrorMessage(e, '读取客户要求失败')
  } finally {
    if (id === requestId) loading.value = false
  }
}

async function append(field) {
  const { clientId } = props
  const module = active.value
  saving.value = true
  try {
    const { added } = await api.post(requirementPath(clientId, module), { values: { [field]: draft.value[field] } })
    ElMessage.success(added ? '已新增客户要求' : '与最新内容一致，无需新增')
    if (props.clientId === clientId && active.value === module) {
      draft.value[field] = ''
      await load()
    }
  } catch (e) {
    ElMessage.error(getLocalizedErrorMessage(e, '保存客户要求失败'))
  } finally {
    saving.value = false
  }
}

watch(() => [props.clientId, active.value], () => { draft.value = {}; void load() }, { immediate: true })
onBeforeUnmount(() => { requestId++ })
</script>

<style scoped>
.requirement-card + .requirement-card { margin-top: 12px; }
.requirement-history { margin-top: 0; padding-inline-start: 22px; }
.requirement-history li + li { margin-top: 12px; }
.requirement-content { white-space: pre-wrap; overflow-wrap: anywhere; }
small { color: var(--el-text-color-secondary); }
.el-input + .el-button { margin-top: 8px; }
</style>
