<template>
  <el-collapse v-if="value" class="original-project-information"><el-collapse-item title="从原母订单复制的完整项目信息" name="original">
    <el-descriptions :column="2" border size="small"><el-descriptions-item v-for="field in fields" :key="field.key" :label="field.label" :span="field.span||1">{{ display(field) }}</el-descriptions-item></el-descriptions>
    <el-descriptions v-for="(file,index) in value.projectFiles||[]" :key="index" :column="2" border size="small" :title="`原项目文件与路径 ${index+1}`"><el-descriptions-item v-for="field in pathFields" :key="field.key" :label="field.label">{{ file[field.key] || '-' }}</el-descriptions-item></el-descriptions>
    <el-table v-if="value.customerChargeItems?.length" :data="value.customerChargeItems" border size="small"><el-table-column prop="itemName" label="收费项" /><el-table-column prop="unitPriceExclTax" label="原单价" /><el-table-column prop="totalExclTax" label="原总价" /><el-table-column prop="currency" label="货币" /></el-table>
  </el-collapse-item></el-collapse>
</template>
<script setup>
import {computed} from 'vue'
import {translationProjectDetailItems} from '@/utils/translationProjectDetail'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {getProjectStatusOptions} from '@/utils/projectStatus'
const props=defineProps({value:Object})
const fields=computed(()=>translationProjectDetailItems.filter(field=>Object.hasOwn(props.value||{},field.key)&&!['pmConfirmedBy'].includes(field.key)))
const pathFields=[['原文路径','storagePath'],['派稿路径','dispatchPath'],['翻译路径','translationPath'],['译员回稿路径','translatorReturnPath'],['客户交付路径','clientDeliveryPath'],['反馈路径','projectFeedbackPath'],['反馈后交付路径','feedbackDeliveryPath'],['文本领域一级','translationDomainLevel1'],['文本领域二级','translationDomainLevel2'],['文件类型','fileType'],['文本类型','fileTypeSecondary'],['文件格式','fileFormat'],['文件属性一级','fileAttributeLevel1'],['文件属性二级','fileAttributeLevel2'],['文件属性三级','fileAttributeLevel3'],['文件难度','fileDifficulty']].map(([label,key])=>({label,key}))
function display(field){const value=props.value?.[field.key];if(value===null||value===undefined||value==='')return '-';if(field.type==='status')return getProjectStatusOptions('translation').find(item=>item.value===value)?.label||value;if(field.formatter)return field.formatter(value,props.value);if(/Time$|At$/.test(field.key))return formatBusinessDateTime(value);return value}
</script>
<style scoped>.original-project-information{margin:16px 0}.el-descriptions{margin:10px 0}:deep(.el-descriptions__content){white-space:pre-wrap;overflow-wrap:anywhere}</style>
