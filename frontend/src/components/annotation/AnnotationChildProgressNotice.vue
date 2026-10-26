<template>
  <el-tooltip v-if="totalCount>0" :content="`子订单进度：已读 ${readCount} / 共 ${totalCount} 条，点击查看`" placement="top">
    <el-button link :type="readCount<totalCount?'danger':'primary'" class="child-progress-notice" :aria-label="`查看子订单进度，已读${readCount}条，共${totalCount}条`" @click.stop="open"><span v-if="showLabel">子订单&nbsp;</span>{{ readCount }}/{{ totalCount }}</el-button>
  </el-tooltip>
  <DraggableFormDialog v-model="visible" title="子订单进度提醒" width="min(900px, calc(100vw - 32px))" top="5vh" class="issue-dialog" append-to-body :z-index="100006">
    <p class="child-progress-hint">已读 {{ readCount }}/{{ totalCount }}。以下记录尚未以相同类型、相同正文登记在当前订单，滚动查看记录后自动计为已读。已读按当前账号保存在本机浏览器，查看不会自动复制进度。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <div ref="recordArea" v-loading="loading"><el-timeline><el-timeline-item v-for="row in rows" :key="`${row.track}:${row.id}`" :timestamp="formatBusinessDateTime(row.effectiveOn)" placement="top"><div class="child-progress-heading"><b>{{ row.orderNo }}</b><el-tag size="small">{{ labels[row.track] }}</el-tag></div><p>{{ row.projectName }}</p><ScreenshotText :text="row.changeNote" /><p class="child-progress-hint">登记人：{{ row.changedByName }} · 登记时间：{{ formatBusinessDateTime(row.changedAt) }}</p><span :data-read-key="row.readKey" class="child-progress-read-marker"></span></el-timeline-item></el-timeline><el-empty v-if="!loading&&!error&&!rows.length" description="暂无未体现的子订单进度" :image-size="48" /></div>
    <template #footer><el-pagination small layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="load" /><el-button :disabled="loading" @click="load">刷新</el-button><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,ref,watch,onBeforeUnmount} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import {getAnnotationChildProgress} from '@/api/annotationProjects'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {useChildProgressRead} from '@/composables/useChildProgressRead'
import '@/views/resource/components/issueDialogs.css'
const props=defineProps({projectId:{type:String,required:true},count:{type:Number,default:0},recordKeys:{type:Array,default:()=>[]},hasChildren:Boolean,showLabel:Boolean})
const visible=ref(false),loading=ref(false),error=ref(''),rows=ref([]),total=ref(0),page=ref(1)
const labels={project:'项目进度',customer:'客户进度',annotator:'标注员情况'}
const freshKeys=ref(null),recordArea=ref()
const keys=computed(()=>freshKeys.value||props.recordKeys)
const totalCount=computed(()=>freshKeys.value?freshKeys.value.length:props.count)
const {count:readCount,mark}=useChildProgressRead(()=>props.projectId,()=>keys.value)
let controller,version=0
let observer
const readTimers=new Map()
function stopObserving(){observer?.disconnect();for(const timer of readTimers.values())clearTimeout(timer);readTimers.clear()}
async function observeRecords(){
  stopObserving();await nextTick();if(!visible.value)return
  observer=new IntersectionObserver(entries=>{for(const entry of entries){const key=entry.target.dataset.readKey;clearTimeout(readTimers.get(key));readTimers.delete(key);if(entry.isIntersecting&&document.visibilityState==='visible')readTimers.set(key,setTimeout(()=>{if(visible.value&&document.visibilityState==='visible')mark(key);readTimers.delete(key)},500))}},{threshold:1})
  for(const node of recordArea.value?.querySelectorAll('[data-read-key]')||[])observer.observe(node)
}
function open(){page.value=1;visible.value=true;void load()}
async function load(){stopObserving();controller?.abort();controller=new AbortController();const current=++version;loading.value=true;error.value='';rows.value=[];try{const data=await getAnnotationChildProgress(props.projectId,{skip:(page.value-1)*20,limit:20},{signal:controller.signal});if(current===version){rows.value=data.items;total.value=data.total;freshKeys.value=data.recordKeys;await observeRecords()}}catch(e){if(current===version&&e.code!=='ERR_CANCELED')error.value=e.detail||e.message||'子订单进度加载失败'}finally{if(current===version)loading.value=false}}
watch(()=>props.recordKeys,()=>{freshKeys.value=null})
watch(()=>props.projectId,()=>{freshKeys.value=null;visible.value=false;controller?.abort();++version})
watch(visible,value=>{if(!value){stopObserving();controller?.abort();++version;loading.value=false}})
onBeforeUnmount(()=>{stopObserving();controller?.abort();++version})
</script>
<style scoped>
.child-progress-read-marker{display:block;height:2px;width:100%}.child-progress-notice{white-space:nowrap;font-size:12px;font-variant-numeric:tabular-nums;min-height:18px;padding:0 3px}.child-progress-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.child-progress-hint{font-size:12px;color:var(--el-text-color-secondary);line-height:1.6}
</style>
