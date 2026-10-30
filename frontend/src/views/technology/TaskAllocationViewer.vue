<template>
  <DraggableFormDialog :model-value="true" title="分工与完成情况" width="min(1250px, calc(100vw - 32px))" top="5vh" append-to-body @update:model-value="value => { if (!value) $emit('close') }">
    <p><strong>{{ task.task_no }} · {{ task.name }}</strong></p>
    <el-table :data="items" row-key="task_id" border><el-table-column prop="executor_name" label="执行人" width="130" /><el-table-column prop="task_no" label="分工编号" width="175" /><el-table-column prop="content" label="具体分工" min-width="240" show-overflow-tooltip /><el-table-column label="预定完成时间" width="180"><template #default="{ row }">{{ formatTime(row.due_at) }}</template></el-table-column><el-table-column label="完成日期" width="160"><template #default="{ row }">{{ row.completed_on || '待完成' }}<el-button link type="primary" @click="editor = { id:row.task_id, mode:'date' }">填写／调整</el-button></template></el-table-column><el-table-column label="是否按时完成" width="150"><template #default="{ row }">{{ row.on_time == null ? '待完成' : row.on_time ? '是' : '否' }}</template></el-table-column><el-table-column label="奖励／抵消奖金" width="170"><template #default="{ row }"><span v-if="row.on_time == null">-</span><el-button v-else link type="primary" @click="editor = { id:row.task_id, mode:'amount' }">{{ row.on_time ? '奖励' : '抵消奖金' }} {{ row.incentive?.amount || '待登记' }}</el-button></template></el-table-column><el-table-column label="具体进度" width="150"><template #default="{ row }"><el-button link type="primary" @click="progressId = row.task_id">{{ row.progress }}% · 修改进度</el-button></template></el-table-column><el-table-column label="操作" width="220" fixed="right"><template #default="{ row }"><TaskCompletionHistory :task-id="row.task_id" /><el-button link type="primary" @click="reportId = row.task_id">加至工作报告</el-button></template></el-table-column></el-table>
    <TaskCompletionHistory :task-id="task.id" />
    <AllocationProgressEditor v-if="progressId" :key="progressId" :task-id="progressId" @close="progressId = null" @changed="$emit('changed')" />
    <TaskCompletionEditor v-if="editor" :key="editor.id + editor.mode" :task-id="editor.id" :initial-mode="editor.mode" @close="editor = null" @changed="changed" />
    <DevelopmentReportDialog v-if="reportId" :task-id="reportId" @close="reportId = null" />
    <template #footer><el-button @click="$emit('close')">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import TaskCompletionEditor from './TaskCompletionEditor.vue'
import TaskCompletionHistory from './TaskCompletionHistory.vue'
import DevelopmentReportDialog from './DevelopmentReportDialog.vue'
import AllocationProgressEditor from './AllocationProgressEditor.vue'
import {formatBusinessDateTimeMinute as formatTime} from '@/utils/datetime'
const props=defineProps({task:{type:Object,required:true}}),emit=defineEmits(['close','changed'])
const editor=ref(null),reportId=ref(null),items=ref([]),progressId=ref(null)
watch(()=>props.task.allocations,value=>{items.value=(value||[]).map(item=>({...item}))},{immediate:true,deep:true})
function changed(value){const row=items.value.find(item=>item.task_id===value.task_id);if(row)Object.assign(row,value);emit('changed')}
</script>
