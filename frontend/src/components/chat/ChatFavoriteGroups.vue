<template>
  <div class="favorite-groups">
    <details v-for="group in groups" :key="group.id" class="favorite-group" :open="searching || group.total <= 5" @dragover.prevent @drop.prevent="drop(group.id)">
      <summary><span v-if="sortable" class="favorite-group__grip" draggable="true" title="拖动调整项目类型顺序" @dragstart.stop="dragType=group.id; $event.dataTransfer.setData('text/plain',group.id)" @dragend="dragType=''">⠿</span><span>{{ group.label }}</span><small>{{ group.total }}</small><button v-if="sortable" type="button" class="favorite-group__front" :aria-label="`${group.label}放在前面`" @click.stop.prevent="$emit('move-type',group.id,null)">置前</button></summary>
      <template v-if="group.dates.length">
        <details v-for="date in group.dates" :key="date.label" class="favorite-date" :open="searching || date.items.length <= 5"><summary><el-icon><Folder /></el-icon>{{ date.label }}<small>{{ date.items.length }}</small></summary><FavoriteRows :items="date.items" @open="$emit('open',$event)" @remove="$emit('remove',$event)" /></details>
      </template>
      <FavoriteRows v-else :items="group.items" @open="$emit('open',$event)" @remove="$emit('remove',$event)" />
    </details>
  </div>
</template>
<script setup>
import {defineComponent,h,ref} from 'vue'
import {ElButton,ElIcon} from 'element-plus'
import {Folder,StarFilled} from '@element-plus/icons-vue'
defineProps({groups:{type:Array,default:()=>[]},sortable:Boolean,searching:Boolean})
const emit=defineEmits(['open','remove','move-type']),dragType=ref('')
function drop(target){if(dragType.value&&dragType.value!==target)emit('move-type',dragType.value,target);dragType.value=''}
const FavoriteRows=defineComponent({props:{items:Array},emits:['open','remove'],setup(props,{emit}){return()=>h('div',props.items.map(item=>h('div',{class:'favorite-row',key:item.key},[
 h('button',{type:'button',class:'favorite-row__open',onClick:()=>emit('open',item)},[h('span',item.title||'未命名会话'),h('small',item.subtitle||'会话')]),
 h(ElButton,{link:true,title:'取消收藏','aria-label':`取消收藏 ${item.title}`,onClick:()=>emit('remove',item)},()=>h(ElIcon,null,()=>h(StarFilled))),
])))}})
</script>
<style scoped>
.favorite-group{margin:5px 0;border-bottom:1px solid #e6edf4;padding-bottom:5px}
.favorite-group>summary,.favorite-date>summary{cursor:pointer;display:flex;align-items:center;gap:8px;padding:8px 4px;color:#334155;font-size:13px;list-style:none}
.favorite-group>summary:before,.favorite-date>summary:before{content:'›';font-size:18px;line-height:1;transition:transform .12s}.favorite-group[open]>summary:before,.favorite-date[open]>summary:before{transform:rotate(90deg)}
.favorite-group summary small{margin-left:auto;color:#64748b;font-size:11px}
.favorite-group__grip{cursor:grab;color:#7891a8;padding:0 3px;user-select:none}
.favorite-group__front{border:0;background:transparent;color:#315d86;font:inherit;font-size:11px;cursor:pointer;padding:3px 5px}
.favorite-date{margin-left:16px}.favorite-date>summary{font-size:12px;color:#526b82}
.favorite-groups :deep(.favorite-row){display:flex;align-items:center;gap:8px;padding:9px 5px 9px 17px;border-top:1px solid #f0f4f8}
.favorite-groups :deep(.favorite-row__open){display:flex;flex-direction:column;gap:5px;flex:1;min-width:0;border:0;background:transparent;text-align:left;color:#334155;font:inherit;cursor:pointer}
.favorite-groups :deep(.favorite-row__open span){overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;font-size:13px}
.favorite-groups :deep(.favorite-row__open small){font-size:11px;color:#7891a8}
.favorite-groups :deep(.favorite-row .el-button){color:#bc8b3c}
</style>
