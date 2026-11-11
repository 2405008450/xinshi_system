<template>
  <el-table v-if="payments.length" :data="payments" border size="small" max-height="300">
    <el-table-column label="阶段" width="80"><template #default="{row}">{{({deposit:'定金',mid:'中期款',final:'尾款'})[row.stage_type]||row.stage_type}}</template></el-table-column>
    <el-table-column prop="stage_no" label="期次" width="65" />
    <el-table-column label="预定金额" min-width="90"><template #default="{row}">{{row.planned_amount??'未填写'}}</template></el-table-column>
    <el-table-column label="实际金额" min-width="90"><template #default="{row}">{{row.actual_amount??'未填写'}}</template></el-table-column>
    <el-table-column label="付款时间" min-width="160"><template #default="{row}">{{row.payment_time?formatDateTime(row.payment_time):'未填写'}}</template></el-table-column>
    <el-table-column prop="payment_method" label="付款方式" min-width="120" />
    <el-table-column label="确认人" min-width="100"><template #default="{row}">{{row.confirmed_by_name || '未记录'}}</template></el-table-column>
    <el-table-column label="确认时间" min-width="175"><template #default="{row}">{{row.confirmed_at ? formatDateTime(row.confirmed_at) : '未记录'}}</template></el-table-column>
    <el-table-column label="支付截图及备注" min-width="220"><template #default="{row}"><ScreenshotText v-if="row.proofs" :text="row.proofs" /><span v-else>-</span></template></el-table-column>
  </el-table>
</template>
<script setup>
import ScreenshotText from './ScreenshotText.vue'
import {formatBusinessDateTime as formatDateTime} from '@/utils/dateTime'
defineProps({payments:{type:Array,default:()=>[]}})
</script>
