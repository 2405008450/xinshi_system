<template>
  <el-descriptions :column="2" border size="small">
    <el-descriptions-item label="订单号">{{ text(row.projectOrderNo) }}</el-descriptions-item>
    <el-descriptions-item label="项目名称">{{ text(row.projectName) }}</el-descriptions-item>
    <el-descriptions-item label="资源">{{ text(row.personName) }}（{{ text(row.resourceCode) }}）</el-descriptions-item>
    <el-descriptions-item label="语言方向">{{ text(row.languageDisplay) }}</el-descriptions-item>
    <el-descriptions-item label="业务类型">{{ label(activityOptions,row.activityType) }}</el-descriptions-item>
    <el-descriptions-item label="工作职责">{{ label(dutyOptions,row.dutyRole) }}</el-descriptions-item>
    <el-descriptions-item label="候选阶段">{{ label(stageOptions,row.candidateStage) }}</el-descriptions-item>
    <el-descriptions-item label="轮次">第 {{ row.roundNo }} 轮</el-descriptions-item>
    <el-descriptions-item label="意愿">{{ label(levelOptions,row.willingnessLevel) }}</el-descriptions-item>
    <el-descriptions-item label="意愿说明" :span="2"><div class="pre-wrap">{{ text(row.willingnessText) }}</div></el-descriptions-item>
    <el-descriptions-item label="报价">{{ quoteText(row) }}</el-descriptions-item>
    <el-descriptions-item label="平台账号">{{ accountText(row) }}</el-descriptions-item>
    <el-descriptions-item label="开始时间">{{ formatDateTime(row.startedAt) }}</el-descriptions-item>
    <el-descriptions-item label="截止时间">{{ formatDateTime(row.deadlineAt) }}</el-descriptions-item>
    <el-descriptions-item label="实际提交时间">{{ formatDateTime(row.submittedAt) }}</el-descriptions-item>
    <el-descriptions-item label="结果">{{ label(resultOptions,row.trialResult) }}</el-descriptions-item>
    <el-descriptions-item label="结果说明" :span="2"><div class="pre-wrap">{{ text(row.resultNote) }}</div></el-descriptions-item>
    <el-descriptions-item label="配合度">{{ label(levelOptions,row.cooperationLevel) }}</el-descriptions-item>
    <el-descriptions-item label="守时度">{{ label(levelOptions,row.punctualityLevel) }}</el-descriptions-item>
    <el-descriptions-item label="配合度说明" :span="2"><div class="pre-wrap">{{ text(row.cooperationNote) }}</div></el-descriptions-item>
    <el-descriptions-item label="守时度说明" :span="2"><div class="pre-wrap">{{ text(row.punctualityNote) }}</div></el-descriptions-item>
    <el-descriptions-item label="总体评分">{{ text(row.overallScore) }}</el-descriptions-item>
    <el-descriptions-item label="最近跟进">{{ latestFollowUpText(row) }}</el-descriptions-item>
    <el-descriptions-item label="项目经理评价" :span="2"><div class="pre-wrap">{{ text(row.managerComment) }}</div></el-descriptions-item>
    <el-descriptions-item v-for="field in customFields" :key="field.id" :label="field.fieldLabel" :span="field.dataType==='textarea'?2:1">{{ customText(row.customValues?.[field.id]) }}</el-descriptions-item>
  </el-descriptions>
</template>

<script setup>
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

defineProps({ row:{type:Object,required:true}, customFields:{type:Array,default:()=>[]} })
const activityOptions={trial:'试标',collection:'试采'}
const dutyOptions={executor:'执行',quality_inspector:'质检'}
const stageOptions={backup:'备选',contacted:'已联系',pending_confirmation:'待确认',confirmed:'已确认',in_progress:'进行中',submitted:'已提交',reviewed:'已评审',withdrawn:'已退出'}
const levelOptions={high:'高',medium:'中',low:'低'}
const resultOptions={passed:'通过',failed:'未通过',partially_passed:'部分通过',withdrawn:'退出'}
const billingOptions={occurrence:'次',item:'条',work_hour:'工作小时',effective_hour:'有效小时'}
const text=value=>value===null||value===undefined||value===''?'-':String(value)
const label=(options,value)=>options[value]||text(value)
const customText=value=>Array.isArray(value)?value.join('、')||'-':value===true?'是':value===false?'否':text(value)
const quoteText=row=>row.quoteAmount?`${row.quoteAmount} ${row.quoteCurrency||'CNY'} / ${label(billingOptions,row.billingUnit)}`:'-'
const accountText=row=>[row.platformName,row.platformAccountNickname].filter(Boolean).join(' · ')||'-'
const latestFollowUpText=row=>row.latestFollowUpAt?`${row.latestFollowUpByName||'未知用户'} · ${formatDateTime(row.latestFollowUpAt)}`:'-'
</script>

<style scoped>.pre-wrap{white-space:pre-wrap;word-break:break-word}</style>
