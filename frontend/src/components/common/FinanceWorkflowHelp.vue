<template>
  <DraggableFormDialog :model-value="modelValue" title="笔译财务流程帮助" class="finance-workflow-help" width="min(1260px, calc(100vw - 32px))" top="4vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <div class="help-search"><el-input v-model="keyword" clearable placeholder="搜索流程、入口或问题，例如：字数 单价" /><span>支持多个关键词；点击图片可查看清晰原图</span></div>
    <div class="help-layout">
      <nav aria-label="帮助目录"><a v-if="showEntries" href="#finance-help-entries" @click.prevent="locate('entries')">各入口的区别与联系</a><a v-for="section in sections" :key="section.id" :href="`#finance-help-${section.id}`" @click.prevent="locate(section.id)">{{section.title}}</a></nav>
      <div ref="content" class="help-content">
        <section v-if="showEntries" id="finance-help-entries"><h2>同一流程，应该从哪里进入？</h2><div class="help-table"><table><thead><tr><th>入口</th><th>适合做什么</th><th>区别与联系</th></tr></thead><tbody><tr v-for="row in financeEntryComparison" :key="row[0]"><td v-for="(cell,index) in row" :key="index">{{cell}}</td></tr></tbody></table></div></section>
        <section v-for="section in sections" :id="`finance-help-${section.id}`" :key="section.id"><h2>{{section.title}}</h2><p v-for="paragraph in section.paragraphs" :key="paragraph">{{paragraph}}</p><figure v-if="screenshots[section.shot]"><el-image :src="screenshots[section.shot].src" :alt="screenshots[section.shot].caption" :preview-src-list="[screenshots[section.shot].src]" preview-teleported fit="contain" /><figcaption>{{screenshots[section.shot].caption}}（点击放大）</figcaption></figure></section>
        <el-empty v-if="!sections.length&&keyword.trim()&&!showEntries" description="没有匹配内容，请尝试其他关键词" />
      </div>
    </div>
    <template #footer><el-button @click="keyword='';locate('entries')">返回目录</el-button><el-button type="primary" @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,ref,watch} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import {financeEntryComparison,financeWorkflowSections} from '@/utils/financeWorkflowHelp'
import {matchesSearchFields} from '@/utils/searchMatching'
import {financeHelpScreenshots as screenshots} from '@/utils/financeHelpScreenshots'
const props=defineProps({modelValue:Boolean}),emit=defineEmits(['update:modelValue'])
const keyword=ref(''),content=ref()
const showEntries=computed(()=>matchesSearchFields(['入口 区别 联系',...financeEntryComparison.flat()],keyword.value))
const sections=computed(()=>financeWorkflowSections.filter(section=>matchesSearchFields([section.title,...section.paragraphs],keyword.value)))
async function locate(id){await nextTick();const target=content.value?.querySelector(`#finance-help-${id}`);target?.scrollIntoView({behavior:'smooth',block:'start'})}
watch(()=>props.modelValue,open=>{if(open){keyword.value='';void nextTick(()=>{if(content.value)content.value.scrollTop=0})}})
</script>
<style scoped>
:global(.finance-workflow-help){display:flex;flex-direction:column;max-height:92vh;overflow:hidden}:global(.finance-workflow-help>.el-dialog__header),:global(.finance-workflow-help>.el-dialog__footer){flex:none}:global(.finance-workflow-help>.el-dialog__body){display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}:global(.finance-workflow-help>.el-dialog__footer){border-top:1px solid var(--el-border-color);background:#fff}.help-search{display:flex;align-items:center;gap:16px;padding-bottom:12px}.help-search>.el-input{width:360px;max-width:100%}.help-search>span,figcaption{font-size:12px;color:var(--el-text-color-secondary)}.help-layout{display:flex;min-height:0;flex:1;gap:24px}.help-layout nav{flex:0 0 220px;overflow:auto;padding-right:12px;border-right:1px solid var(--el-border-color)}nav a{display:block;color:var(--el-text-color-regular);text-decoration:none;padding:9px 4px;line-height:1.5}nav a:hover{color:var(--el-color-primary)}.help-content{flex:1;min-width:0;overflow:auto;scroll-behavior:smooth;padding-right:12px}.help-content section{margin-bottom:30px;scroll-margin-top:8px}.help-content h2{font-size:18px;margin:6px 0 16px}.help-content p{font-size:14px;line-height:1.9;margin:10px 0}.help-table{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.7}th,td{padding:10px;border:1px solid var(--el-border-color);text-align:left;vertical-align:top}th{background:var(--el-fill-color-light)}figure{margin:18px 0}figure .el-image{display:block;width:100%;border:1px solid var(--el-border-color);cursor:zoom-in}figcaption{margin-top:6px}@media(max-width:760px){.help-layout{flex-direction:column;gap:10px}.help-layout nav{flex:0 0 92px;border-right:0;border-bottom:1px solid var(--el-border-color)}nav a{display:inline-block;padding:6px 10px}.help-search{flex-wrap:wrap}.help-content{padding-right:0}}
</style>
