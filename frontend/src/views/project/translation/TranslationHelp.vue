<template>
  <el-card class="translation-help" shadow="never">
    <template #header><div class="help-heading"><div><h2>笔译操作帮助</h2><p>先登记订单，再补齐统计、安排任务和发送通知。</p></div><el-tag effect="plain">更新于 {{ translationHelpUpdatedAt }}</el-tag></div>
      <div class="help-search"><el-input v-model="keyword" clearable placeholder="搜索帮助，例如：母订单 子订单、路径、字数、邮件" aria-label="搜索笔译帮助" @keyup.enter="applySearch" /><el-button type="primary" @click="applySearch">查询</el-button><span>{{ visibleSections.length }} 个章节</span></div>
    </template>
    <div class="help-layout">
      <nav class="help-directory" aria-label="笔译帮助目录"><template v-for="group in groups" :key="group"><strong>{{ group }}</strong><button v-for="section in visibleSections.filter(item=>item.group===group)" :key="section.id" type="button" :class="{active:activeId===section.id}" :aria-current="activeId===section.id?'location':undefined" @click="goTo(section.id)">{{ section.title }}</button></template></nav>
      <main ref="content" class="help-content" aria-label="帮助正文" @scroll.passive="trackSection">
        <el-empty v-if="!visibleSections.length" description="没有匹配的帮助内容"><el-button @click="keyword='';applySearch()">清空搜索</el-button></el-empty>
        <section v-for="section in visibleSections" :id="'translation-help-'+section.id" :key="section.id" :ref="el=>sectionElements[section.id]=el" class="help-section">
          <h3>{{ section.title }}</h3><p v-if="section.summary" class="section-summary">{{ section.summary }}</p>
          <div v-if="section.headers" class="help-table-scroll"><table><thead><tr><th v-for="heading in section.headers" :key="heading">{{ heading }}</th></tr></thead><tbody><tr v-for="(row,index) in section.rows" :key="index"><td v-for="(cell,column) in row" :key="column">{{ cell }}</td></tr></tbody></table></div>
          <ol v-if="section.steps"><li v-for="step in section.steps" :key="step">{{ step }}</li></ol>
          <p v-for="paragraph in section.paragraphs||[]" :key="paragraph">{{ paragraph }}</p>
          <pre v-if="section.example" class="order-example">{{ section.example }}</pre>
          <el-alert v-if="section.tip" :title="section.tip" type="info" :closable="false" show-icon />
          <el-alert v-if="section.warning" :title="section.warning" type="warning" :closable="false" show-icon />
          <figure v-if="section.image"><el-image :src="section.image.src" :alt="section.image.alt" :preview-src-list="[section.image.src]" preview-teleported loading="lazy" fit="contain" /><figcaption>{{ section.image.caption }}</figcaption></figure>
        </section>
      </main>
    </div>
  </el-card>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch,nextTick} from 'vue'
import {matchesSearchFields} from '@/utils/searchMatching'
import {translationHelpSections,translationHelpUpdatedAt} from './translationHelpContent'
const keyword=ref(''),appliedKeyword=ref(''),activeId=ref('order-basics'),content=ref(null),sectionElements={}
const visibleSections=computed(()=>translationHelpSections.filter(section=>matchesSearchFields([section.title,section.summary,...(section.paragraphs||[]),...(section.steps||[]),...(section.rows||[]).flat(),section.tip,section.warning,section.example],appliedKeyword.value)))
const groups=computed(()=>[...new Set(visibleSections.value.map(section=>section.group))])
let timer
async function applySearch(){clearTimeout(timer);appliedKeyword.value=keyword.value;activeId.value=visibleSections.value[0]?.id||'';await nextTick();if(content.value)content.value.scrollTop=0}
watch(keyword,value=>{clearTimeout(timer);if(!value.trim())applySearch();else timer=setTimeout(applySearch,400)})
function goTo(id){activeId.value=id;const element=sectionElements[id],body=content.value;if(element&&body)body.scrollTo({top:body.scrollTop+element.getBoundingClientRect().top-body.getBoundingClientRect().top-12,behavior:'smooth'})}
function trackSection(){const top=content.value?.getBoundingClientRect().top||0;const current=visibleSections.value.filter(section=>(sectionElements[section.id]?.getBoundingClientRect().top??Infinity)<=top+90).at(-1);if(current)activeId.value=current.id}
onBeforeUnmount(()=>clearTimeout(timer))
</script>
<style scoped>
.translation-help{display:flex;flex-direction:column;min-height:0;height:100%;border-radius:var(--radius-lg,12px)}.translation-help :deep(.el-card__header){flex:none;padding:16px 22px}.translation-help :deep(.el-card__body){flex:1;min-height:0;padding:0;overflow:hidden}.help-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.help-heading h2{margin:0;font-size:21px;color:#172033}.help-heading p{margin:6px 0 12px;font-size:14px;color:#64748b}.help-search{display:flex;align-items:center;gap:12px;max-width:900px}.help-search .el-input{flex:1}.help-search>span{white-space:nowrap;font-size:13px;color:#64748b}.help-layout{display:grid;grid-template-columns:260px minmax(0,1fr);height:100%;min-height:0}.help-directory{overflow-y:auto;padding:18px 14px;background:#f8fafc;border-right:1px solid #e2e8f0}.help-directory>strong{display:block;margin:8px 10px 10px;font-size:13px;color:#64748b}.help-directory button{display:block;width:100%;border:0;background:transparent;text-align:left;line-height:1.6;padding:10px 12px;margin:3px 0;border-radius:7px;color:#475569;cursor:pointer;font:inherit;font-size:13px}.help-directory button:hover,.help-directory button.active{background:#e2e8f0;color:#172033}.help-directory button.active{font-weight:600}.help-content{overflow-y:auto;padding:8px 28px 24px;min-width:0;position:relative}.help-section{max-width:1120px;margin:0 auto;padding:24px 0;border-bottom:1px solid #e2e8f0;scroll-margin-top:16px}.help-section:last-child{border:0}.help-section h3{margin:0 0 12px;color:#172033;font-size:20px}.help-section p,.help-section li{font-size:15px;line-height:1.85;color:#334155}.help-section p{margin:12px 0}.help-section li{padding-left:4px;margin:8px 0}.help-section ol{padding-left:24px}.section-summary{font-weight:500}.help-table-scroll{overflow-x:auto;margin:16px 0}.help-section table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.8}.help-section th,.help-section td{border:1px solid #dce4ef;padding:12px 14px;text-align:left;vertical-align:top}.help-section th{background:#f1f5f9;color:#334155}.help-section td:first-child{min-width:140px;font-weight:500}.help-section .el-alert{margin:14px 0}.help-section :deep(.el-alert__title){font-size:14px;line-height:1.8}.order-example{font-family:Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:18px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;line-height:2}.help-section figure{margin:20px 0 4px}.help-section .el-image{display:block;border:1px solid #dce4ef;border-radius:8px;background:#fff;cursor:zoom-in}.help-section figcaption{font-size:12px;color:#64748b;margin-top:8px;line-height:1.7}@media(max-width:900px){.help-layout{grid-template-columns:190px minmax(0,1fr)}.help-content{padding:8px 18px 20px}}@media(max-width:640px){.help-heading .el-tag{display:none}.help-layout{display:flex;flex-direction:column}.help-directory{display:flex;gap:6px;flex:none;overflow-x:auto;overflow-y:hidden;padding:8px;border-right:0;border-bottom:1px solid #e2e8f0}.help-directory>strong{display:none}.help-directory button{width:auto;min-width:160px;margin:0;white-space:nowrap}.help-content{flex:1;min-height:0;padding:0 14px 20px}.help-heading h2{font-size:19px}.help-search{gap:8px}.help-search>span{display:none}.translation-help :deep(.el-card__header){padding:14px}.help-section h3{font-size:18px}}
</style>
