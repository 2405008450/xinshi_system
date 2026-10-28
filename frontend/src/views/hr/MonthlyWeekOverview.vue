<template>
  <div class="month-week-scroll">
    <table class="month-week-table">
      <thead><tr><th>排班周（周一至周日）</th><th v-for="shift in plans[0]?.shifts||[]" :key="shift.code">{{shift.label}}<small v-for="period in shift.periods" :key="period">{{period}}</small></th></tr></thead>
      <tbody><tr v-for="plan in plans" :key="plan.week_start" :data-week="plan.week_start">
        <th>{{plan.week_start}}<br>至 {{plan.week_end}}<small v-if="plan.week_start.slice(0,7)!==month||plan.week_end.slice(0,7)!==month">跨月周，与相邻月份共用安排</small></th>
        <td v-for="shift in plan.shifts" :key="shift.code">
          <template v-for="department in plan.departments" :key="department.code"><div v-if="people(plan,shift.code,department.code).length" class="month-week-group"><strong>{{department.label}}</strong><div v-for="person in people(plan,shift.code,department.code)" :key="person.user_id">{{person.name}} <el-tag v-if="person.fixed" size="small" type="info">固定</el-tag><small v-if="!person.active">已停用</small></div></div></template>
          <span v-if="!plan.assignments.some(row=>row.shift===shift.code)" class="empty">暂无安排</span>
        </td>
      </tr></tbody>
    </table>
  </div>
</template>
<script setup>
defineProps({plans:{type:Array,default:()=>[]},month:String})
const people=(plan,shift,department)=>plan.assignments.filter(row=>row.shift===shift&&row.department===department)
</script>
<style scoped>.month-week-scroll{overflow-x:auto}.month-week-table{width:100%;min-width:1050px;border-collapse:collapse;table-layout:fixed}.month-week-table td,.month-week-table th{border:1px solid #dbe3ec;padding:10px;vertical-align:top;overflow-wrap:anywhere}.month-week-table th{background:#f8fafc}.month-week-table small{display:block;font-size:11px;font-weight:400;color:#64748b;margin:4px 0}.month-week-group{margin-bottom:10px;font-size:13px;line-height:1.8}.month-week-group strong{font-size:12px;color:#64748b}.empty{color:#94a3b8;font-size:12px}</style>
