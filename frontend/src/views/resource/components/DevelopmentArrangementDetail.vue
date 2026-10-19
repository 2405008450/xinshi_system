<template>
  <el-popover v-model:visible="opened" trigger="click" placement="left" :width="760" :popper-options="popoverOptions" :title="account ? `${account.name} · 安排详情` : `${chineseDate(day.work_date)} · 每日安排详情`" popper-class="development-detail arrangement-detail">
    <template #reference><el-button link type="primary">查看详情</el-button></template>
    <div class="development-detail-body">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="日期">{{ chineseDate(day.work_date) }}</el-descriptions-item>
        <el-descriptions-item label="记录状态">{{ day.revision ? '已保存' : '尚未保存' }}</el-descriptions-item>
        <el-descriptions-item label="每日备注" :span="2">{{ day.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-empty v-if="!accounts.length" description="当天尚未安排账号" />
      <section v-for="item in accounts" :key="item.id" class="arrangement-account-detail">
        <h4>{{ item.path }}</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="大类">{{ item.categoryLabel }}</el-descriptions-item>
          <el-descriptions-item label="平台">{{ item.platformName }}</el-descriptions-item>
          <el-descriptions-item label="账号">{{ item.accountName }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ item.cell?.owner_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成状态" :span="2">{{ item.placeholder ? '暂无账号' : !item.cell ? '未安排' : item.cell.completed ? '已完成' : '未完成' }}</el-descriptions-item>
          <el-descriptions-item label="平台／账号情况说明" :span="2">{{ item.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="语种／开拓方向" :span="2"><span v-for="(target, index) in item.cell?.targets || []" :key="arrangementTargetKey(target)">{{ index ? '、' : '' }}{{ target.label }}{{ target.active === false ? `（${target.inactive_reason}）` : '' }}</span><span v-if="!item.cell?.targets?.length">-</span></el-descriptions-item>
          <el-descriptions-item label="岗位目标" :span="2">{{ item.cell?.role_tags?.join('、') || '-' }}</el-descriptions-item>
          <template v-for="target in (item.cell?.targets || []).filter(t => t.kind === 'request_project')" :key="target.request_id">
            <el-descriptions-item :label="`${target.request_no || '需求'} · 语言城市`" :span="2">{{ target.scope?.map(scope => scope.label).join('；') || '未配置语种与城市' }}</el-descriptions-item>
            <el-descriptions-item label="安排备注" :span="2">{{ target.arrangement_note || '-' }}</el-descriptions-item>
          </template>
          <el-descriptions-item label="关联项目" :span="2"><DevelopmentArrangementProject v-for="project in item.cell?.projects || []" :key="arrangementProjectKey(project)" :project="project" /><span v-if="!item.cell?.projects?.length">-</span></el-descriptions-item>
          <el-descriptions-item label="账号备注" :span="2">{{ item.cell?.remarks || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成操作人">{{ item.cell?.completed_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ chineseTime(item.cell?.completed_at) }}</el-descriptions-item>
        </el-descriptions>
        <DevelopmentArrangementHistory v-if="opened && item.cell?.id" :day="day" :cell="item.cell" />
      </section>
    </div>
  </el-popover>
</template>
<script setup>
import { computed, ref } from 'vue'
import { arrangementProjectKey, arrangementTargetKey, arrangementChineseDate as chineseDate, arrangementChineseTime as chineseTime, groupArrangementAccounts, arrangementTableRows, arrangementPopoverOptions as popoverOptions } from '@/utils/resourceArrangements'
import DevelopmentArrangementProject from './DevelopmentArrangementProject.vue'
import DevelopmentArrangementHistory from './DevelopmentArrangementHistory.vue'
const opened = ref(false)
const props = defineProps({ day: { type: Object, required: true }, account: { type: Object, default: null }, options: { type: Object, default: () => ({}) } })
const accounts = computed(() => props.account ? [props.account] : arrangementTableRows(groupArrangementAccounts(props.options, props.day.cells, { includeUnarranged: false, includeEmpty: false })))
</script>
<style>
.arrangement-account-detail h4{margin:16px 0 8px}.arrangement-account-detail .arrangement-project-link{margin-right:10px}
</style>
