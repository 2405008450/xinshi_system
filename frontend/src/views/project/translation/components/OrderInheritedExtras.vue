<template>
  <div class="order-inherited-extras">
    <el-form-item label="服务内容" prop="serviceContent">
      <el-select v-model="model.serviceContent" filterable allow-create default-first-option clearable placeholder="自动复制上级，可调整"><el-option v-for="value in serviceOptions" :key="value" :label="value" :value="value" /></el-select>
      <OrderFieldHint :order="model" field="serviceContent" />
    </el-form-item>
    <el-form-item v-for="item in textFields" :key="item.key" :label="item.label" :prop="item.key">
      <el-input v-model="model[item.key]" type="textarea" :rows="2" :class="{'supplementary-notes':item.key==='remarks'}" placeholder="自动复制上级，可单独编辑" />
      <OrderFieldHint :order="model" :field="item.key" />
    </el-form-item>
  </div>
</template>
<script setup>
import OrderFieldHint from './OrderFieldHint.vue'
defineProps({model:{type:Object,required:true}})
const serviceOptions=['翻译','Word排版','PPT排版','InDesign排版','CorelDRAW排版','Illustrator排版','CAD排版','翻译+InDesign排版','翻译+CorelDRAW排版','翻译+Illustrator排版','翻译+CAD排版','其他排版','翻译+其他排版']
const textFields=[{key:'customerRequirementProfessional',label:'客户专业要求'},{key:'customerRequirementSpecial',label:'客户特殊要求'},{key:'remarks',label:'补充说明'}]
</script>
<style scoped>
.order-inherited-extras{width:100%}.supplementary-notes :deep(.el-textarea__inner){color:#2563eb}
</style>
