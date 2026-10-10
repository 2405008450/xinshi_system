<template>
  <el-popover trigger="click" placement="left" :width="760" :popper-options="popoverOptions" :title="`${chineseDate(day.work_date)} · 每日安排详情`" popper-class="development-detail arrangement-detail">
    <template #reference><el-button link type="primary">查看详情</el-button></template>
    <div class="development-detail-body">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="日期">{{ chineseDate(day.work_date) }}</el-descriptions-item>
        <el-descriptions-item label="记录状态">{{ day.revision ? '已保存' : '尚未保存' }}</el-descriptions-item>
        <el-descriptions-item label="每日备注" :span="2">{{ day.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-empty v-if="!day.cells.length" description="当天尚未安排账号" />
      <section v-for="cell in day.cells" :key="cell.platform_id" class="arrangement-account-detail">
        <h4>{{ cell.platform_name }}</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="负责人">{{ cell.owner_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成状态">{{ cell.completed ? '已完成' : '未完成' }}</el-descriptions-item>
          <el-descriptions-item label="语种／开拓方向" :span="2"><span v-for="(target, index) in cell.targets" :key="arrangementTargetKey(target)">{{ index ? '、' : '' }}{{ target.label }}{{ target.active === false ? `（${target.inactive_reason}）` : '' }}</span><span v-if="!cell.targets.length">-</span></el-descriptions-item>
          <el-descriptions-item label="岗位目标" :span="2">{{ cell.role_tags?.join('、') || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联项目" :span="2"><DevelopmentArrangementProject v-for="project in cell.projects" :key="arrangementProjectKey(project)" :project="project" /><span v-if="!cell.projects.length">-</span></el-descriptions-item>
          <el-descriptions-item label="账号备注" :span="2">{{ cell.remarks || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成操作人">{{ cell.completed_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ chineseTime(cell.completed_at) }}</el-descriptions-item>
        </el-descriptions>
      </section>
    </div>
  </el-popover>
</template>
<script setup>
import { arrangementProjectKey, arrangementTargetKey, arrangementChineseDate as chineseDate, arrangementChineseTime as chineseTime } from '@/utils/resourceArrangements'
import DevelopmentArrangementProject from './DevelopmentArrangementProject.vue'
defineProps({ day: { type: Object, required: true } })
const popoverOptions = { modifiers: [{ name:'flip', options:{ fallbackPlacements:[] } }, { name:'preventOverflow', options:{ altAxis:true, tether:false, padding:16 } }] }
</script>
<style>
.arrangement-account-detail h4{margin:16px 0 8px}.arrangement-account-detail .arrangement-project-link{margin-right:10px}
</style>
