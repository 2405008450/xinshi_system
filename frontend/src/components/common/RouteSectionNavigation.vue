<template>
  <el-card class="route-section-navigation" shadow="never">
    <el-tabs :model-value="active" :before-leave="navigate" :aria-label="label">
      <el-tab-pane v-for="item in items" :key="item.path" :label="item.label" :name="item.path" />
    </el-tabs>
  </el-card>
</template>
<script setup>
import {computed} from 'vue'
import {useRoute,useRouter} from 'vue-router'
const props=defineProps({items:{type:Array,required:true},label:{type:String,default:'二级导航'}})
const route=useRoute(),router=useRouter()
const active=computed(()=>props.items.find(item=>route.path===item.path||route.path.startsWith(item.path+'/'))?.path||'')
async function navigate(path){if(path===active.value)return true;await router.push(path);return active.value===path}
</script>
<style scoped>
.route-section-navigation{flex:none;min-width:0;border-color:var(--color-border);border-radius:var(--radius-lg)}.route-section-navigation :deep(.el-card__body){padding:0 20px}.route-section-navigation :deep(.el-tabs__header){margin:0}.route-section-navigation :deep(.el-tabs__content){display:none}.route-section-navigation :deep(.el-tabs__nav-wrap::after){height:1px}.route-section-navigation :deep(.el-tabs__item){height:36px;font-size:15px}
</style>
