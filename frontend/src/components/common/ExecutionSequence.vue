<template>
  <div class="execution-sequence" aria-label="执行顺序">
    <template v-for="(step,index) in sequence" :key="step.id">
      <span v-if="index" class="sequence-arrow" aria-hidden="true">→</span>
      <span class="execution-step" :class="{'is-current':step.id===currentId,'is-completed':step.status==='completed'}" :title="labels[step.status]||step.status">{{index+1}}. {{step.assignee_name}}</span>
    </template>
    <span v-if="!sequence.length">-</span>
  </div>
</template>
<script setup>
defineProps({sequence:{type:Array,default:()=>[]},currentId:{type:String,default:''}})
const labels={pending:'待进行',in_progress:'进行中',completed:'已完成'}
</script>
<style scoped>.execution-sequence{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12px}.execution-step{padding:3px 6px;background:#f1f5f9;border-radius:4px}.execution-step.is-current{background:#dbeafe;color:#1d4ed8;font-weight:600}.execution-step.is-completed{border-bottom:2px solid #22c55e}.sequence-arrow{color:#64748b}</style>
