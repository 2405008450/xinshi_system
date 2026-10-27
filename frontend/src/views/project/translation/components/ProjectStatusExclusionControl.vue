<template>
  <el-popover trigger="click" placement="bottom-end" :width="380" popper-class="arrangement-filter-popover project-status-exclusion-popover">
    <template #reference><el-button :type="modelValue.length?'primary':''" :class="{'is-active-filter':modelValue.length}" :aria-pressed="modelValue.length>0" plain>排除状态<span v-if="modelValue.length">（{{modelValue.length}}）</span></el-button></template>
    <p>勾选的项目状态将从列表中排除。</p>
    <el-checkbox-group :model-value="modelValue" class="exclusion-options" @update:model-value="$emit('update:modelValue',$event)"><el-checkbox v-for="option in statuses" :key="option.value" :value="option.value">{{option.label}}</el-checkbox></el-checkbox-group>
    <div class="filter-footer"><el-button link @click="$emit('update:modelValue',[])">取消全部</el-button><el-button link type="primary" @click="$emit('update:modelValue',[...DEFAULT_ARRANGEMENT_EXCLUSIONS])">恢复默认</el-button></div>
  </el-popover>
</template>
<script setup>
import {DEFAULT_ARRANGEMENT_EXCLUSIONS} from '@/utils/arrangementFilters'
defineProps({modelValue:{type:Array,default:()=>[]},statuses:{type:Array,default:()=>[]}})
defineEmits(['update:modelValue'])
</script>
<style scoped>
.is-active-filter{--el-button-bg-color:#f1f5f9;--el-button-text-color:#334155;--el-button-border-color:#94a3b8;--el-button-hover-bg-color:#e2e8f0;--el-button-hover-text-color:#334155;--el-button-hover-border-color:#94a3b8;--el-button-active-bg-color:#e2e8f0;--el-button-active-border-color:#64748b}.exclusion-options{display:grid;grid-template-columns:1fr 1fr;gap:2px 10px}.exclusion-options :deep(.el-checkbox){margin-right:0}.filter-footer{display:flex;justify-content:flex-end;gap:12px;margin-top:12px;border-top:1px solid #e2e8f0;padding-top:10px}
</style>
<style>.project-status-exclusion-popover{max-width:calc(100vw - 32px)!important;max-height:min(560px,calc(100vh - 120px));overflow-y:auto}</style>
