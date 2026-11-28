<template>
 <section class="personal-folders" @dragover.prevent @drop.prevent="dropExternal($event,null)">
  <p v-if="error" role="alert">{{ error }} <el-button link @click="load">重试</el-button></p>
  <el-tree ref="tree" :data="treeData" highlight-current node-key="id" :props="{label:'name'}" :default-expanded-keys="expanded" draggable :allow-drop="allowDrop" :allow-drag="()=>!busy" :expand-on-click-node="true" @node-drop="moved" @node-expand="nodeExpanded" @node-collapse="nodeCollapsed" @node-click="clickNode">
   <template #default="{node,data}"><span class="personal-node" @dragover.prevent.stop @drop.prevent="dropExternal($event,data.session?data.parentId:data.id)"><span>{{ data.session?'☏':'▱' }} {{ data.name }}</span><span class="personal-actions"><button v-if="!data.session && node.level<5" type="button" title="新建子文件夹" @click.stop="edit(data.id)">＋</button><button type="button" title="重命名" @click.stop="edit(data.parentId,data)">✎</button><button type="button" :title="data.session?'移出此文件夹':'删除文件夹（不删除会话）'" @click.stop="remove(data)">×</button></span></span></template>
  </el-tree>
  <small>将群聊或单聊拖入文件夹，仅本人可见。</small>
  <DraggableFormDialog v-model="dialog" title="个人文件夹" width="min(420px,calc(100vw - 32px))" append-to-body :z-index="110020"><AppForm :model="form" @submit.prevent="submit"><el-form-item :label="form.session?'会话显示名称':'文件夹名称'"><el-input v-model="form.name" maxlength="120" autofocus @keyup.enter="submit"/></el-form-item></AppForm><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="busy" @click="submit">保存</el-button></template></DraggableFormDialog>
 </section>
</template>
<script setup>
import {computed,onMounted,ref,reactive,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {chatRequest} from '@/api/projectChat'
const props=defineProps({expandAll:{type:Boolean,default:false},expandRevision:Number})
const emit=defineEmits(['open','count','select'])
const rows=ref([]),revision=ref(0),busy=ref(false),error=ref(''),dialog=ref(false),tree=ref(),form=reactive({id:'',parentId:null,name:'',session:null})
const identity=localStorage.getItem('user_id'),storageKey=`xinshi.personalFolderExpanded.${identity}`
let saved=[];try{saved=JSON.parse(localStorage.getItem(storageKey)||'[]')}catch{}
const expanded=ref(Array.isArray(saved)?saved:[])
const treeData=computed(()=>{const map=new Map(rows.value.map(row=>[row.id,{...row,children:[]}])),roots=[];for(const row of map.values()){if(row.parentId&&map.has(row.parentId))map.get(row.parentId).children.push(row);else roots.push(row)}return roots})
function remember(){localStorage.setItem(storageKey,JSON.stringify(expanded.value))}
function nodeExpanded(data){expanded.value=[...new Set([...expanded.value,data.id])];remember()}
function nodeCollapsed(data){expanded.value=expanded.value.filter(id=>id!==data.id);remember()}
watch(()=>[props.expandAll,props.expandRevision],([value])=>{expanded.value=value?rows.value.filter(row=>!row.session).map(row=>row.id):[];remember();for(const row of rows.value){const node=tree.value?.getNode(row.id);if(node)node.expanded=value}})
async function load(){try{const data=await chatRequest('personal-folders');if(identity!==localStorage.getItem('user_id'))return;rows.value=data.nodes;revision.value=data.revision;error.value=''}catch(e){error.value=e.detail||'个人目录加载失败'}}
async function persist(next){if(busy.value)return false;busy.value=true;try{const data=await chatRequest('personal-folders',{method:'put',data:{revision:revision.value,nodes:next}});if(identity!==localStorage.getItem('user_id'))return false;rows.value=data.nodes;revision.value=data.revision;return true}catch(e){ElMessage.error(e.detail||'保存失败');await load();return false}finally{busy.value=false}}
function edit(parentId=null,row=null){Object.assign(form,{id:row?.id||'',parentId,name:row?.name||'',session:row?.session||null});dialog.value=true}
async function submit(){if(!form.name.trim()||busy.value)return;const item={id:form.id||crypto.randomUUID(),parentId:form.parentId,name:form.name.trim(),...(form.session?{session:form.session}:{})};const next=form.id?rows.value.map(row=>row.id===form.id?item:row):[...rows.value,item];if(await persist(next)){dialog.value=false;if(form.parentId)nodeExpanded({id:form.parentId})}}
async function remove(data){if(busy.value)return;if(!data.session){try{await ElMessageBox.confirm('删除此文件夹及其中的个人归档？会话和聊天记录保留。','删除个人文件夹',{type:'warning'})}catch{return}}const removed=new Set([data.id]);let changed=true;while(changed){changed=false;for(const row of rows.value)if(removed.has(row.parentId)&&!removed.has(row.id)){removed.add(row.id);changed=true}}await persist(rows.value.filter(row=>!removed.has(row.id)))}
function selectFolder(data={id:null,name:'自定义'}){const included=new Set(data.id?[data.id]:[]);let changed=true;while(changed){changed=false;for(const row of rows.value)if((data.id==null||included.has(row.parentId))&&!included.has(row.id)){included.add(row.id);changed=true}}emit('select',{id:data.id||'personal:root',name:data.name,sessions:rows.value.filter(row=>row.session&&included.has(row.id)).map(row=>({...row.session,title:row.name}))})}
function clickNode(data){if(data.session)emit('open',data.session);else selectFolder(data)}
function height(node){return (node.data.session?0:1)+Math.max(0,...(node.childNodes||[]).map(height))}
function allowDrop(drag,target,type){if(busy.value||type==='inner'&&target.data.session)return false;const level=type==='inner'?target.level+1:target.level;return level-1+height(drag)<=5}
async function moved(drag,target,type){const parentId=type==='inner'?target.data.id:target.data.parentId;const item={...drag.data,parentId};delete item.children;const next=rows.value.filter(row=>row.id!==item.id);const index=next.findIndex(row=>row.id===target.data.id);next.splice(index<0?next.length:index+(type==='after'?1:0),0,item);await persist(next)}
async function dropExternal(event,parentId){const raw=event.dataTransfer?.getData('application/x-xinshi-chat-session');if(!raw||busy.value)return;event.stopPropagation();try{const session=JSON.parse(raw);if(!session.projectId||!['annotation','translation','discussion','direct'].includes(session.projectType))return;if(rows.value.some(row=>row.parentId===parentId&&row.session?.key===session.key)){ElMessage.info('此文件夹已经有该会话');return}await persist([...rows.value,{id:crypto.randomUUID(),parentId,name:session.title||'未命名会话',session:{key:session.key,projectId:session.projectId,projectType:session.projectType,title:session.title,subtitle:session.subtitle}}]);if(parentId)nodeExpanded({id:parentId})}catch{ElMessage.error('拖入的会话格式不正确')}}
watch(rows,value=>emit('count',value.filter(row=>row.session).length))
onMounted(load)
defineExpose({edit,selectFolder})
</script>
<style scoped>.personal-folders{min-height:50px;padding:6px 0}.personal-folders>small{display:block;color:#64748b;font-size:10px;padding:8px}.personal-node{display:flex;align-items:center;justify-content:space-between;gap:5px;width:100%;min-width:0}.personal-node>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.personal-actions{display:flex;flex:none}.personal-actions button{border:0;background:transparent;cursor:pointer;padding:4px;color:#475569}.personal-folders :deep(.el-tree){background:transparent;font-size:12px}.personal-folders :deep(.el-tree-node__content){min-height:32px}</style>
