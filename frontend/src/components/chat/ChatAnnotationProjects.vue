<template>
  <section class="chat-annotation-projects" aria-label="会话中的标注项目管理">
    <el-config-provider :z-index="10000">
      <AnnotationProjects ref="mainList" embedded :my-projects="myProjects" @open-conversation="$emit('open-conversation')" @open-child-management="openChildren" />
      <DraggableFormDialog v-model="childrenVisible" :title="childContext.orderScope==='grandchild'?'标注三级订单管理':'标注子订单管理'" width="min(1500px, calc(100vw - 32px))" top="5vh" class="chat-child-orders-dialog" append-to-body destroy-on-close :z-index="9980" @closed="mainList?.refresh()">
        <AnnotationProjects v-if="childrenVisible" :key="`${childContext.parentProjectId}:${childContext.orderScope}`" embedded order-scope="child" :child-parent-id="childContext.parentProjectId" :child-order-scope="childContext.orderScope" @open-conversation="$emit('open-conversation')" @open-child-management="openChildren" @close-child-management="childrenVisible=false" />
        <template #footer><el-button @click="childrenVisible=false">关闭</el-button></template>
      </DraggableFormDialog>
    </el-config-provider>
  </section>
</template>
<script setup>
import { defineAsyncComponent, onBeforeUnmount,ref } from 'vue'
import { useRouter } from 'vue-router'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
const AnnotationProjects = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const emit = defineEmits(['navigate', 'open-conversation'])
defineProps({myProjects:Boolean})
const childrenVisible=ref(false),childContext=ref({parentProjectId:'',orderScope:'child'})
const mainList=ref()
function openChildren(context){childContext.value=context;childrenVisible.value=true}
// 跳转子订单、试标等原有页面时收起会话，让目标页面可见。
const stop = useRouter().afterEach((to, from, failure) => {
  if (!failure && to.fullPath !== from.fullPath) emit('navigate')
})
onBeforeUnmount(stop)
</script>
<style scoped>
.chat-annotation-projects{height:100%;min-height:0;display:flex;flex-direction:column}.chat-annotation-projects :deep(.annotation-card){flex:1;min-height:0}
</style>
<style>
.chat-child-orders-dialog{display:flex;flex-direction:column;height:66.67vh;max-height:90vh;overflow:hidden}
.chat-child-orders-dialog>.el-dialog__header,.chat-child-orders-dialog>.el-dialog__footer{flex:none}
.chat-child-orders-dialog>.el-dialog__body{min-height:0;flex:1;overflow-y:auto}
.chat-child-orders-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color-lighter)}
</style>
