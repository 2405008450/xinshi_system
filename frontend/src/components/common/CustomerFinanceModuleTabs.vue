<template>
  <slot v-if="!enabled" :name="module" />
  <el-tabs v-else :model-value="active" class="customer-finance-module-tabs" @update:model-value="emit('update:modelValue',$event)">
    <el-tab-pane v-for="item in modules" :key="item.key" :label="item.label" :name="item.key">
      <slot v-if="item.key===module" :name="item.key" />
      <template v-else-if="active===item.key">
        <el-empty v-if="!clientId" description="请先关联客户，再查看对应项目的财务记录" />
        <component v-else :is="views[item.key]" :module="item.key" :client-id="clientId" client-scope />
      </template>
    </el-tab-pane>
  </el-tabs>
</template>
<script setup>
import { computed, defineAsyncComponent } from 'vue'
const props=defineProps({module:{type:String,required:true},modelValue:String,clientId:{type:[String,Number],default:''},enabled:{type:Boolean,default:true}})
const emit=defineEmits(['update:modelValue'])
const active=computed(()=>props.modelValue||props.module)
const modules=[{key:'translation',label:'笔译财务'},{key:'interpretation',label:'口译财务'},{key:'annotation',label:'标注财务'},{key:'recruitment',label:'招聘财务'}]
const views={
  translation:defineAsyncComponent(()=>import('@/views/project/translation/CustomerFinance.vue')),
  interpretation:defineAsyncComponent(()=>import('@/views/project/interpretation/CustomerFinance.vue')),
  annotation:defineAsyncComponent(()=>import('@/views/project/ProjectCustomerFinance.vue')),
  recruitment:defineAsyncComponent(()=>import('@/views/project/ProjectCustomerFinance.vue')),
}
</script>
<style scoped>
.customer-finance-module-tabs { min-width:0; }
.customer-finance-module-tabs :deep(.el-tabs__nav-wrap) { max-width:100%; }
</style>
