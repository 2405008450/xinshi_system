<template>
 <DraggableFormDialog v-model="visible" class="chat-favorite-tag-dialog" title="消息收藏标签" width="min(520px, calc(100vw - 32px))" top="12vh" append-to-body :z-index="110020" destroy-on-close>
  <p class="hint">标签名称和颜色共享，其他人可从下拉中选择；收藏消息仅自己可见。</p>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <AppForm :model="form" data-auto-draft="off" @submit.prevent @keydown.capture="tagKeydown" @compositionstart="enterReady=false">
   <el-form-item label="标签"><el-select ref="tagSelect" v-model="form.ids" :reserve-keyword="false" @change="enterReady=true" multiple filterable allow-create default-first-option :multiple-limit="20" popper-class="chat-favorite-tag-options" placeholder="选择已有标签，或输入新名称后回车" aria-label="消息收藏标签" :loading="loading" :disabled="loading||saving" style="width:100%"><template #tag><span v-for="id in form.ids" :key="id" class="favorite-tag-selection"><ChatFavoriteTagLabel :name="catalog.find(tag=>tag.id===id)?.name||id" :color="color(id)"/><button type="button" :disabled="saving" :aria-label="`移除标签 ${catalog.find(tag=>tag.id===id)?.name||id}`" @mousedown.prevent.stop @click.stop="form.ids=form.ids.filter(value=>value!==id)">×</button></span></template><el-option v-for="tag in catalog" :key="tag.id" :value="tag.id" :label="tag.name"><ChatFavoriteTagLabel :name="tag.name" :color="tag.color"/></el-option></el-select></el-form-item>
  </AppForm>
  <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading||!favorited" @click="save">保存</el-button></template>
 </DraggableFormDialog>
</template>
<script setup>
import {reactive,ref,nextTick} from 'vue'
import {chatRequest} from '@/api/projectChat'
import {ElMessage} from 'element-plus'
import ChatFavoriteTagLabel from './ChatFavoriteTagLabel.vue'
const emit=defineEmits(['saved'])
const visible=ref(false),loading=ref(false),saving=ref(false),error=ref(''),favorited=ref(false),catalog=ref([]),form=reactive({ids:[]})
const enterReady=ref(false),tagSelect=ref()
function tagKeydown(event){if(event.isComposing||event.keyCode===229){enterReady.value=false;return}if(event.key!=='Enter'){if(event.key.length===1||['ArrowDown','ArrowUp','Backspace','Delete','Escape'].includes(event.key))enterReady.value=false;return}if(event.repeat){event.preventDefault();event.stopPropagation();return}if(enterReady.value){event.preventDefault();event.stopPropagation();enterReady.value=false;if(tagSelect.value)tagSelect.value.expanded=false;void save()}}
let context,version=0
const color=id=>catalog.value.find(tag=>tag.id===id)?.color||'#2563eb'
async function open(kind,cid,mid){const current=++version;context={kind,cid,mid};enterReady.value=false;visible.value=true;loading.value=true;error.value='';form.ids=[];favorited.value=false
 try{const [options,data]=await Promise.all([chatRequest('favorite-tags'),chatRequest(`favorite-tags/${kind}/${cid}/${mid}`)]);if(current!==version)return;catalog.value=options.items||[];form.ids=data.tags.map(tag=>tag.id);favorited.value=data.favorited;if(!data.favorited)error.value='请先收藏这条消息，再设置标签'}catch(e){if(current===version)error.value=e.detail||e.message||'标签加载失败'}finally{if(current===version){loading.value=false;await nextTick();tagSelect.value?.focus()}}}
async function save(){if(saving.value||loading.value||!favorited.value)return;const current=version,scope={...context};saving.value=true;error.value=''
 try{const ids=[];for(const value of form.ids){let tag=catalog.value.find(tag=>tag.id===value);if(!tag){tag=await chatRequest('favorite-tags',{method:'post',data:{name:value}});if(!catalog.value.some(row=>row.id===tag.id))catalog.value.push(tag)}ids.push(tag.id)}const data=await chatRequest(`favorite-tags/${scope.kind}/${scope.cid}/${scope.mid}`,{method:'put',data:{tagIds:[...new Set(ids)]}});if(current!==version)return;emit('saved',data.tags);visible.value=false;window.dispatchEvent(new Event('chat-favorite-tags-changed'));ElMessage.success('收藏标签已保存')}
 catch(e){if(current===version)error.value=e.detail||e.message||'保存标签失败'}finally{saving.value=false}}
defineExpose({open})
</script>
<style>.chat-favorite-tag-dialog.el-dialog{display:flex;flex-direction:column;max-height:85vh;overflow:hidden}.chat-favorite-tag-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.chat-favorite-tag-dialog .el-dialog__header,.chat-favorite-tag-dialog .el-dialog__footer{flex:none}.chat-favorite-tag-options.el-popper{z-index:110030!important}</style>
<style scoped>.hint{font-size:12px;color:#64748b;line-height:1.7}.favorite-tag-selection{display:inline-flex;align-items:center;gap:5px;padding:2px 6px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:3px;max-width:100%}.favorite-tag-selection>button{border:0;background:transparent;color:#64748b;cursor:pointer;padding:0 2px;font-size:16px}.favorite-tag-selection>button:focus-visible{outline:2px solid #5479be}</style>
