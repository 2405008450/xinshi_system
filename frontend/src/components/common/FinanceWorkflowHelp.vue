<template>
  <DraggableFormDialog :model-value="modelValue" :title="title" class="finance-workflow-help" width="min(1260px, calc(100vw - 32px))" top="4vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <div class="help-search"><el-input v-model="keyword" clearable :placeholder="searchPlaceholder" aria-label="搜索帮助" /><span>更新于 {{financeHelpUpdatedAt}} · 支持多个关键词<span v-if="!helpSections"> · 点击图片查看原图</span></span></div>
    <div class="help-layout">
      <nav aria-label="帮助目录">
        <a v-if="overview" href="#finance-help-workflow-overview" @click.prevent="locate(overview.id)">{{ overview.title }}</a>
        <div v-if="sections.length" class="help-directory-heading">详细操作</div>
        <a v-for="section in sections" :key="section.id" :href="`#finance-help-${section.id}`" @click.prevent="locate(section.id)">{{ section.title }}</a>
      </nav>
      <div ref="content" class="help-content">
        <section v-for="section in visibleSections" :id="`finance-help-${section.id}`" :key="section.id">
          <h2>{{ section.title }}</h2>
          <ol v-if="section.steps" class="help-workflow-steps">
            <li v-for="step in section.steps" :key="step">{{ step }}</li>
          </ol>
          <p v-for="paragraph in section.paragraphs" :key="paragraph">{{ paragraph }}</p>
          <div v-if="section.table" class="help-table">
            <table>
              <thead><tr><th v-for="heading in section.table.headers" :key="heading" scope="col">{{ heading }}</th></tr></thead>
              <tbody>
                <tr v-for="row in section.table.rows" :key="row[0]">
                  <th scope="row">{{ row[0] }}</th>
                  <td v-for="(cell,index) in row.slice(1)" :key="index">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <figure v-if="screenshots[section.shot]">
            <el-image :src="screenshots[section.shot].src" :alt="screenshots[section.shot].caption" :preview-src-list="[screenshots[section.shot].src]" preview-teleported fit="contain" />
            <figcaption>{{ screenshots[section.shot].caption }}（点击放大）</figcaption>
          </figure>
        </section>
        <el-empty v-if="!visibleSections.length" description="没有匹配内容，请尝试其他关键词" />
      </div>
    </div>
    <template #footer><el-button @click="resetSearch">返回目录</el-button><el-button type="primary" @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,ref,watch} from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import {financeEntryComparison,financeWorkflowOverview,financeWorkflowRules,financeWorkflowSections,financeWorkflowSync,financeHelpUpdatedAt} from '@/utils/financeWorkflowHelp'
import {matchesSearchFields} from '@/utils/searchMatching'
import {financeHelpScreenshots as screenshots} from '@/utils/financeHelpScreenshots'
const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '财务管理帮助 · 笔译' },
  searchPlaceholder: { type: String, default: '搜索流程、入口或问题，例如：字数 单价' },
  helpSections: Array,
})
const emit = defineEmits(['update:modelValue'])
const keyword=ref(''),content=ref()
const financeEntries={id:'entries',title:'各入口的区别与联系',table:{headers:['入口','适合做什么','区别与联系'],rows:financeEntryComparison}}
function matchesSection(section){
  return matchesSearchFields([section.title,...(section.steps||[]),...(section.paragraphs||[]),
    ...(section.table?.headers||[]),...(section.table?.rows||[]).flat()],keyword.value)
}
const overview=computed(()=>matchesSection(financeWorkflowOverview)?financeWorkflowOverview:null)
const sections=computed(()=>[financeWorkflowSync,...financeWorkflowRules,
  ...(props.helpSections || [financeEntries,...financeWorkflowSections])].filter(matchesSection))
const visibleSections=computed(()=>overview.value?[overview.value,...sections.value]:sections.value)
async function locate(id){await nextTick();const target=content.value?.querySelector(`#finance-help-${id}`);target?.scrollIntoView({behavior:'smooth',block:'start'})}
async function resetSearch() {
  keyword.value = ''
  await nextTick()
  if (content.value) content.value.scrollTop = 0
}
watch(()=>props.modelValue,open=>{if(open) void resetSearch()})
</script>
<style scoped>
:global(.finance-workflow-help){display:flex;flex-direction:column;max-height:92vh;overflow:hidden}:global(.finance-workflow-help>.el-dialog__header),:global(.finance-workflow-help>.el-dialog__footer){flex:none}:global(.finance-workflow-help>.el-dialog__body){display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}:global(.finance-workflow-help>.el-dialog__footer){border-top:1px solid var(--el-border-color);background:#fff}.help-search{display:flex;align-items:center;gap:16px;padding-bottom:12px}.help-search>.el-input{width:360px;max-width:100%}.help-search>span,figcaption{font-size:12px;color:var(--el-text-color-secondary)}.help-layout{display:flex;min-height:0;flex:1;gap:24px}.help-layout nav{flex:0 0 220px;overflow:auto;padding-right:12px;border-right:1px solid var(--el-border-color)}nav a{display:block;color:var(--el-text-color-regular);text-decoration:none;padding:9px 4px;line-height:1.5}nav a:hover{color:var(--el-color-primary)}.help-content{flex:1;min-width:0;overflow:auto;scroll-behavior:smooth;padding-right:12px}.help-content section{margin-bottom:30px;scroll-margin-top:8px}.help-content h2{font-size:18px;margin:6px 0 16px}.help-content p{font-size:14px;line-height:1.9;margin:10px 0}.help-table{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.7}th,td{padding:10px;border:1px solid var(--el-border-color);text-align:left;vertical-align:top}th{background:var(--el-fill-color-light)}figure{margin:18px 0}figure .el-image{display:block;width:100%;border:1px solid var(--el-border-color);cursor:zoom-in}figcaption{margin-top:6px}@media(max-width:760px){.help-layout{flex-direction:column;gap:10px}.help-layout nav{flex:0 0 92px;border-right:0;border-bottom:1px solid var(--el-border-color)}nav a{display:inline-block;padding:6px 10px}.help-search{flex-wrap:wrap}.help-content{padding-right:0}}
</style>
<style scoped>
.help-directory-heading {
  margin: 16px 4px 4px;
  color: var(--el-text-color-secondary);
  font-weight: 600;
}
.help-workflow-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin: 0 0 16px;
  padding: 0;
  list-style: none;
}
.help-workflow-steps li {
  position: relative;
  padding: 6px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  font-weight: 600;
}
.help-workflow-steps li:not(:last-child)::after {
  position: absolute;
  inset-inline-start: calc(100% + 4px);
  content: '→' / '';
  color: var(--el-text-color-secondary);
}
.help-table tbody th { background: var(--el-fill-color-lighter); }
@media(max-width:760px) {
  .help-directory-heading { display: inline-block; margin: 0 4px; }
}
</style>
