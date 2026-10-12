<template>
  <el-popover trigger="click" placement="left" :width="760" :popper-options="channelPopoverOptions" :title="row.parent_id ? '账号详情' : '渠道详情'" popper-class="channel-details">
    <template #reference><el-button link type="primary">查看详情</el-button></template>
    <div class="channel-details-body">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item v-if="row.parent_name" label="所属平台" :span="2">{{ row.parent_name }}</el-descriptions-item>
        <el-descriptions-item v-for="column in channelColumns" :key="column.key" :label="column.label" :span="['purpose','description'].includes(column.key) ? 2 : 1">{{ value(column.key) }}</el-descriptions-item>
      </el-descriptions>
    </div>
  </el-popover>
</template>

<script setup>
import { channelColumns, channelDateTime, channelMembersText, channelPopoverOptions } from '@/utils/resourceChannels'
import { categoryOptions } from '@/utils/resourceDevelopment'
const props = defineProps({ row: { type: Object, required: true } })
function value(key) {
  if (key === 'category') return categoryOptions.find(item => item.value === props.row.category)?.label || '-'
  if (['maintainers','users'].includes(key)) return channelMembersText(props.row[key])
  if (key.endsWith('_at')) return channelDateTime(props.row[key])
  return props.row[key] || '-'
}
</script>

<style>
.channel-details { max-width:calc(100vw - 32px); box-sizing:border-box; }
.channel-details-body { max-height:min(560px,calc(100vh - 140px)); overflow-y:auto; }
.channel-details .el-descriptions__table { table-layout:fixed; width:100%; }
.channel-details .el-descriptions__cell { white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
