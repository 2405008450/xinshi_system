<template>
  <div class="inheritance-panel">
    <span>{{ overrides === null ? '历史订单各字段独立维护' : '未独立修改的业务字段跟随上级更新' }}；客户经理、项目经理各订单独立管理；恢复继承在保存后生效。</span>
    <el-popover trigger="click" placement="bottom-end" :width="360">
      <template #reference><el-button plain>恢复继承{{ modelValue.length ? `（${modelValue.length}）` : '' }}</el-button></template>
      <div class="inheritance-options"><el-checkbox-group :model-value="modelValue" @update:model-value="$emit('update:modelValue',$event)"><el-checkbox v-for="field in independentFields" :key="field.key" :label="field.key">{{ field.label }}</el-checkbox></el-checkbox-group></div>
      <el-empty v-if="!independentFields.length" description="所有业务字段均在继承上级" :image-size="48" />
      <el-button link @click="$emit('update:modelValue',independentFields.map(field=>field.key))">全部恢复</el-button>
      <el-button link @click="$emit('update:modelValue',[])">取消选择</el-button>
    </el-popover>
  </div>
</template>
<script setup>
import {computed} from 'vue'
const props=defineProps({overrides:{type:Array,default:null},customFields:{type:Array,default:()=>[]},modelValue:{type:Array,default:()=>[]}})
defineEmits(['update:modelValue'])
const labels={project_name:'项目名称',project_types:'项目类型',task_description:'具体任务',client_id:'客户',sub_client_id:'子客户',contact_name:'联系人',customer_order_no:'客户单号',email_subject_preview:'邮件主题',project_status:'项目进度',status_effective_on:'状态生效时间',priority:'优先次序',language_region:'语言地区',potential_demand:'需求量',project_path:'项目路径',quotation_path:'报价单路径',contract_path:'合同路径',task_dispatched_at:'任务派发时间',task_submitted_at:'任务提交时间',customer_consultation_time:'客户咨询时间',customer_confirmation_time:'客户确认时间',price_items:'客户报价',assignees:'人员安排',role_assignments:'项目专员、项目助理'}
const independentFields=computed(()=>[...Object.entries(labels).map(([key,label])=>({key,label})),...props.customFields.map(field=>({key:`custom:${field.id}`,label:field.fieldLabel}))].filter(field=>props.overrides===null||(props.overrides.includes('*')&&!props.overrides.includes(`inherit:${field.key}`))||props.overrides.includes(field.key)))
</script>
<style scoped>
.inheritance-panel{display:flex;align-items:center;gap:12px;padding:10px 0;font-size:12px;flex-wrap:wrap}.inheritance-panel>span{flex:1;color:var(--el-text-color-secondary)}.inheritance-options{max-height:min(400px,calc(100vh - 150px));overflow-y:auto}.inheritance-options .el-checkbox{display:flex;margin:0}
</style>
