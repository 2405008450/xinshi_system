<template>
  <div class="discussion-mention-input">
    <el-button text size="small" aria-label="提及讨论人员" :disabled="disabled" @click="insert">@ 提及</el-button>
    <el-input ref="field" :show-screenshot-tools="false" :model-value="modelValue" type="textarea" :rows="3" resize="none" maxlength="10000" placeholder="输入讨论消息，@ 提及人员或所有人" :disabled="disabled" @update:model-value="value=>$emit('update:modelValue',value)" @uploading-change="$emit('uploading-change',$event)" @input="changed" @click="changed" @keydown="keydown" @compositionstart="composing=true;open=false" @compositionend="composing=false;changed()" @blur="open=false" />
    <div v-if="open" class="discussion-mention-menu" role="listbox" aria-label="选择讨论提及人员" @mousedown.prevent>
      <p>@所有人仅提醒当前会话成员</p><button v-for="(person,index) in candidates" :key="person.id" type="button" role="option" :aria-selected="index===selected" :class="{'is-active':index===selected}" @mouseenter="selected=index" @click="choose(person)"><span>{{person.name}}</span><small v-if="person.all">当前会话所有人</small><small v-else-if="person.outside">发送后加入会话</small><ChatDesktopPresence v-if="!person.all" :online="presence[person.id]" :loading="presenceLoading" /></button><small v-if="!candidates.length">没有匹配的人员</small>
    </div>
  </div>
</template>
<script setup>
import {computed,nextTick,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import ChatDesktopPresence from './ChatDesktopPresence.vue'
import {useDesktopPresence} from '@/composables/useDesktopPresence'
import {matchesSearch} from '@/utils/searchMatching'
const props=defineProps({modelValue:{type:String,default:''},users:{type:Array,default:()=>[]},disabled:Boolean,selectedUsers:{type:Array,default:()=>[]}})
const emit=defineEmits(['update:modelValue','selection','send','uploading-change'])
const field=ref(),open=ref(false),query=ref(''),selected=ref(0),composing=ref(false),chosen=ref([...props.selectedUsers])
const current=localStorage.getItem('user_id')||''
let trigger=-1
const mentioned=(text,name)=>{const token=`@${name}`;for(let at=text.indexOf(token);at>=0;at=text.indexOf(token,at+1)){if(!/^[\p{L}\p{N}_]/u.test(text.slice(at+token.length,at+token.length+1)))return true}return false}
const candidates=computed(()=>[{id:'__all__',name:'所有人',all:true},...props.users.filter(person=>person.id!==current)].filter(person=>matchesSearch(person.name,query.value)))
const {statuses:presence,loading:presenceLoading}=useDesktopPresence(computed(()=>candidates.value.filter(person=>!person.all).map(person=>person.id)),open)
watch([()=>props.selectedUsers,()=>props.modelValue],([selectedUsers,value])=>{
  // 文本与外部选人状态同一轮更新；保留本控件刚选中的人员，避免互相覆盖。
  const people=[...new Map([...selectedUsers,...chosen.value].map(person=>[person.id,person])).values()]
  const valid=value?people.filter(person=>mentioned(value,person.name)):[]
  chosen.value=valid
  if(valid.length===selectedUsers.length&&valid.every((person,index)=>person.id===selectedUsers[index].id&&person.name===selectedUsers[index].name&&!!person.all===!!selectedUsers[index].all))return
  emit('selection',{mentionedUserIds:valid.filter(person=>!person.all).map(person=>person.id),mentionAll:valid.some(person=>person.all),selectedUsers:valid})
},{flush:'post'})
async function changed(){if(composing.value)return;await nextTick();const input=field.value?.textarea;if(!input)return;const cursor=input.selectionStart;const match=props.modelValue.slice(0,cursor).match(/(?:^|[^A-Za-z0-9@])@([^\s@]*)$/u);if(!match||input.selectionStart!==input.selectionEnd){open.value=false;return}trigger=cursor-match[1].length-1;query.value=match[1];selected.value=0;open.value=true}
async function choose(person){if(trigger<0)return;if(!person.all&&!chosen.value.some(value=>value.id===person.id)&&chosen.value.filter(value=>!value.all).length>=20){ElMessage.warning('每条消息最多提及20人');return}const input=field.value.textarea;const token=`@${person.name} `;const end=trigger+token.length;if(!chosen.value.some(value=>value.id===person.id))chosen.value.push(person);emit('update:modelValue',props.modelValue.slice(0,trigger)+token+props.modelValue.slice(input.selectionStart));open.value=false;await nextTick();field.value.focus();input.setSelectionRange(end,end)}
async function insert(){const input=field.value?.textarea;const start=input?.selectionStart??props.modelValue.length,end=input?.selectionEnd??start;const token=(start&&!/\s$/.test(props.modelValue.slice(0,start))?' ':'')+'@';emit('update:modelValue',props.modelValue.slice(0,start)+token+props.modelValue.slice(end));await nextTick();field.value?.focus();input?.setSelectionRange(start+token.length,start+token.length);changed()}
function keydown(event){if(event.isComposing||composing.value||event.keyCode===229)return;if(open.value){if(event.key==='Escape'){event.preventDefault();event.stopPropagation();open.value=false;return}if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();selected.value=(selected.value+(event.key==='ArrowDown'?1:-1)+candidates.value.length)%Math.max(1,candidates.value.length);return}if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();if(candidates.value[selected.value])choose(candidates.value[selected.value]);return}}if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();emit('send')}}
defineExpose({focus:()=>field.value?.focus()})
</script>
<style scoped>
.discussion-mention-input{position:relative}.discussion-mention-menu{position:absolute;bottom:100%;left:0;width:min(390px,100%);max-height:280px;overflow:auto;z-index:5;padding:6px;border:1px solid #dbe3ec;border-radius:8px;box-shadow:0 8px 24px #0f172a22;background:white;box-sizing:border-box}.discussion-mention-menu p{font-size:11px;color:#64748b;margin:5px}.discussion-mention-menu button{display:flex;align-items:center;gap:10px;width:100%;border:0;background:white;color:#334155;padding:9px 8px;text-align:left;cursor:pointer}.discussion-mention-menu button.is-active{background:#eff6ff}.discussion-mention-menu small{font-size:10px;color:#64748b}.discussion-mention-menu button>span{flex:1}
</style>
