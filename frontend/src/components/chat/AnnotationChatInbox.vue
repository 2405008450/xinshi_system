<template>
  <el-config-provider :z-index="favoritesZ">
    <el-popover v-if="allowed" v-model:visible="favoritesVisible" title="收藏夹" :z-index="favoritesZ" trigger="click" placement="bottom-end" :width="520" popper-class="annotation-favorites-popover">
      <template #reference><el-badge is-dot :hidden="!mentionTotal"><el-button class="annotation-favorites-trigger" text :circle="!menuLayout" aria-label="收藏夹" title="收藏夹" @click.stop="toggleFavorites"><el-icon :size="18"><Star /></el-icon><span v-if="menuLayout">收藏夹</span></el-button></el-badge></template>
      <div class="annotation-favorites-content">
        <div class="favorite-tabs" role="tablist" aria-label="收藏分类"><button v-for="tab in favoriteTabs" :key="tab.id" type="button" role="tab" :aria-selected="favoriteTab===tab.id" :class="{'is-active':favoriteTab===tab.id}" @click="favoriteTab=tab.id">{{ tab.label }}<small>{{ tabCount(tab.id) }}</small></button></div>
        <ChatFavoriteMessages v-if="favoriteTab==='messages'" @locate="openMessage" @total="messageTotal=$event" /><template v-else><div class="annotation-favorites-heading"><strong>{{ activeLabel }}</strong><span>{{ filteredFavorites.length }} / {{ currentItems.length }}</span>
          <el-popover v-model:visible="candidateVisible" title="加入收藏" :draft-filter="false" trigger="click" placement="left-start" :width="500" :z-index="favoritesZ+2" popper-class="favorite-candidates-popover">
            <template #reference><el-button size="small" :icon="Star">加入收藏</el-button></template>
            <div class="favorite-candidates"><el-input v-model="candidateKeyword" clearable placeholder="搜索项目名称、订单号或会话" aria-label="搜索加入收藏候选项" @keyup.enter="searchCandidates" /><div class="favorite-candidates__list"><el-empty v-if="!candidateItems.length" description="当前目录没有待收藏的项目或会话" :image-size="40" /><div v-for="item in pagedCandidates" :key="item.key" class="favorite-candidate"><span><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span><el-button link :icon="Star" :loading="favoriteBusy.has(item.key)" @click="addFavorite(item)">加入收藏</el-button></div></div><ChatListPagination v-model:page="candidatePage" v-model:page-size="candidatePageSize" :total="candidateItems.length" :teleported="false" /></div>
          </el-popover>
          <el-button v-if="favoriteTab==='projects' && canReadProjects" size="small" plain @click="openProjectPicker">项目筛选</el-button>
        </div>
        <div class="annotation-favorites-search" data-auto-draft="off"><el-input v-model="favoritesKeyword" clearable placeholder="搜索收藏的项目名称、订单号或会话" aria-label="搜索收藏项目" @keyup.enter="searchFavorites" /><el-button @click="searchFavorites">查询</el-button></div>
        <div class="favorite-list-tools"><small v-if="favoriteTab==='projects'">拖动类型调整顺序，或点击“置前”</small><el-button v-if="favoriteTab==='projects' && canReadProjects" link @click="favoritesVisible=false; recoveryVisible=true">恢复已移除的项目</el-button></div>
        <p v-if="error" role="alert">{{ error }} <el-button link @click="refresh">重试</el-button></p>
        <div class="annotation-favorites-list"><el-empty v-if="!error && !filteredFavorites.length" :description="appliedKeyword ? '没有匹配的收藏' : '点击「加入收藏」选择项目或会话'" :image-size="45" /><ChatFavoriteGroups :groups="groups" :sortable="favoriteTab==='projects'" :searching="!!appliedKeyword" @open="open" @remove="removeFavorite" @move-type="moveType" /></div>
        <div class="annotation-favorites-paging"><ChatListPagination v-model:page="favoritesPage" v-model:page-size="favoritesPageSize" :total="filteredFavorites.length" :teleported="false" /><p role="status">{{ filteredFavorites.length ? `当前显示第 ${(favoritesPage-1)*favoritesPageSize+1}–${Math.min(favoritesPage*favoritesPageSize,filteredFavorites.length)} 条，共 ${filteredFavorites.length} 条` : '共 0 条' }}</p></div>
      </template></div>
    </el-popover>
    <ChatAnnotationProjectPicker favorite-mode v-model="projectPickerVisible" @joined="refresh" />
    <ChatFavoriteRecovery v-model="recoveryVisible" @restored="refresh" />
  </el-config-provider>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {Star} from '@element-plus/icons-vue'
import ChatAnnotationProjectPicker from './ChatAnnotationProjectPicker.vue'
import ChatFavoriteRecovery from './ChatFavoriteRecovery.vue'
import ChatListPagination from './ChatListPagination.vue'
import ChatFavoriteGroups from './ChatFavoriteGroups.vue'
import ChatFavoriteMessages from './ChatFavoriteMessages.vue'
import {chatOverlayZIndex} from '@/utils/chatOverlay'
import {useProjectChatDock} from '@/composables/useProjectChatDock'
import {useChatFavorites} from '@/composables/useChatFavorites'
import {useChatSessionCategories} from '@/composables/useChatSessionCategories'
import {useAnnotationFollowed} from '@/composables/useAnnotationFollowed'
import {hasPermission} from '@/utils/permission'
import {matchesSearchFields} from '@/utils/searchMatching'
import {sessionFolderNodes} from '@/utils/chatSessionFolders'
import {favoriteTabs,favoriteClassification,favoriteProjectDate,favoriteGroups,normalizeFavoriteTypeOrder,isSessionFavorite} from '@/utils/chatFavorites'
defineProps({menuLayout:Boolean})
const emit=defineEmits(['conversation-opened','navigate'])
const {openChat}=useProjectChatDock(),{sessions,refresh,setFavorite,busy:favoriteBusy}=useChatFavorites()
const {mentionTotal,error}=useAnnotationFollowed(),{categories}=useChatSessionCategories()
const nodes=computed(()=>sessionFolderNodes(categories.items,{technicalAccess:categories.technicalAccess}))
const favoritesZ=ref(2110),favoritesVisible=ref(false),candidateVisible=ref(false),projectPickerVisible=ref(false),recoveryVisible=ref(false)
const favoriteTab=ref('messages'),messageTotal=ref(''),activeLabel=computed(()=>favoriteTabs.find(row=>row.id===favoriteTab.value).label)
const canReadProjects=computed(()=>hasPermission('projects:read')),allowed=computed(()=>canReadProjects.value||sessions.value.length>0)
const orderKey=`xinshi.chatFavoriteTypeOrder.${localStorage.getItem('user_id')||'anonymous'}`
let savedOrder;try{savedOrder=JSON.parse(localStorage.getItem(orderKey)||'null')}catch{}
const typeOrder=ref(normalizeFavoriteTypeOrder(savedOrder))
const catalog=computed(()=>sessions.value.map(row=>({...row,projectType:row.kind||row.projectType})))
const favorites=computed(()=>catalog.value.filter(isSessionFavorite))
const tabCount=id=>id==='messages'?messageTotal.value:favorites.value.filter(row=>favoriteClassification(row,nodes.value).tab===id).length
function sorted(items){return [...items].sort((a,b)=>{const ac=favoriteClassification(a,nodes.value),bc=favoriteClassification(b,nodes.value);return (favoriteTab.value==='projects'?typeOrder.value.indexOf(ac.type)-typeOrder.value.indexOf(bc.type):0)||favoriteProjectDate(b).localeCompare(favoriteProjectDate(a))||String(a.title).localeCompare(String(b.title),'zh-CN')})}
const currentItems=computed(()=>sorted(favorites.value.filter(row=>favoriteClassification(row,nodes.value).tab===favoriteTab.value)))
const favoritesKeyword=ref(''),appliedKeyword=ref(''),favoritesPage=ref(1),favoritesPageSize=ref(20)
let searchTimer,candidateTimer
function searchFavorites(){clearTimeout(searchTimer);appliedKeyword.value=favoritesKeyword.value.trim();favoritesPage.value=1}
watch(favoritesKeyword,value=>{clearTimeout(searchTimer);if(!value.trim())searchFavorites();else searchTimer=setTimeout(searchFavorites,400)})
const filteredFavorites=computed(()=>currentItems.value.filter(row=>matchesSearchFields([row.title,row.subtitle],appliedKeyword.value)))
const pagedFavorites=computed(()=>filteredFavorites.value.slice((favoritesPage.value-1)*favoritesPageSize.value,favoritesPage.value*favoritesPageSize.value))
const groups=computed(()=>favoriteGroups(pagedFavorites.value,filteredFavorites.value,favoriteTab.value,nodes.value,typeOrder.value))
watch([()=>filteredFavorites.value.length,favoritesPageSize],([total])=>favoritesPage.value=Math.min(favoritesPage.value,Math.max(1,Math.ceil(total/favoritesPageSize.value))))
const candidateKeyword=ref(''),appliedCandidateKeyword=ref(''),candidatePage=ref(1),candidatePageSize=ref(20)
function searchCandidates(){clearTimeout(candidateTimer);appliedCandidateKeyword.value=candidateKeyword.value.trim();candidatePage.value=1}
watch(candidateKeyword,value=>{clearTimeout(candidateTimer);if(!value.trim())searchCandidates();else candidateTimer=setTimeout(searchCandidates,400)})
const candidateItems=computed(()=>sorted(catalog.value.filter(row=>!isSessionFavorite(row)&&favoriteClassification(row,nodes.value).tab===favoriteTab.value&&matchesSearchFields([row.title,row.subtitle],appliedCandidateKeyword.value))))
const pagedCandidates=computed(()=>candidateItems.value.slice((candidatePage.value-1)*candidatePageSize.value,candidatePage.value*candidatePageSize.value))
watch(()=>candidateItems.value.length,total=>candidatePage.value=Math.min(candidatePage.value,Math.max(1,Math.ceil(total/candidatePageSize.value))))
watch(favoriteTab,()=>{favoritesKeyword.value='';searchFavorites();candidateKeyword.value='';searchCandidates();candidateVisible.value=false})
function moveType(type,before){const values=typeOrder.value.filter(id=>id!==type);values.splice(before?Math.max(0,values.indexOf(before)):0,0,type);typeOrder.value=values;favoritesPage.value=1;try{localStorage.setItem(orderKey,JSON.stringify(values))}catch{}}
function toggleFavorites(event){favoritesZ.value=chatOverlayZIndex(event.currentTarget);favoritesVisible.value=!favoritesVisible.value}
function open(row){openChat({projectId:row.projectId,projectType:row.projectType,title:row.title,subtitle:row.subtitle});favoritesVisible.value=false;emit('conversation-opened')}
function openMessage(row){openChat({projectId:row.projectId,projectType:row.projectType,title:row.title,subtitle:row.subtitle,messageId:row.messageId});favoritesVisible.value=false;emit('conversation-opened')}
function openProjectPicker(){candidateVisible.value=false;favoritesVisible.value=false;projectPickerVisible.value=true}
async function addFavorite(row){try{await setFavorite(row,true);ElMessage.success('已加入收藏')}catch(e){ElMessage.error(e.detail||e.message||'加入收藏失败，请重试')}}
async function removeFavorite(row){try{await setFavorite(row,false)}catch(e){ElMessage.error(e.detail||e.message||'取消收藏失败，请重试')}}
watch(favoritesVisible,value=>{if(value)refresh();else candidateVisible.value=false})
onBeforeUnmount(()=>{clearTimeout(searchTimer);clearTimeout(candidateTimer)})
</script>
<style>
.annotation-favorites-popover,.favorite-candidates-popover{max-width:calc(100vw - 24px)!important}
.annotation-favorites-popover .app-window-popover__body{display:flex;flex-direction:column;overflow:hidden;max-height:min(600px,calc(100vh - 150px))}
.favorite-candidates-popover .app-window-popover__body{display:flex;flex-direction:column;overflow:hidden;max-height:min(500px,calc(100vh - 150px))}
</style>
<style scoped>
.annotation-favorites-trigger{color:var(--color-text-secondary)}
.annotation-favorites-content{display:flex;flex:1;flex-direction:column;max-height:min(600px,calc(100vh - 150px));min-height:0;overflow:hidden}
.favorite-tabs{display:flex;gap:5px;padding:8px 0 10px;flex:none}.favorite-tabs button{flex:1;min-width:0;padding:8px 3px;border:1px solid #dce6ef;border-radius:6px;color:#526b82;background:#f8fafc;font:inherit;font-size:12px;cursor:pointer}.favorite-tabs button.is-active{color:#233d57;background:#e6eef6;border-color:#9db7cf}.favorite-tabs small{margin-left:4px;color:#64748b;font-size:10px}
.annotation-favorites-heading{display:flex;flex:none;align-items:center;gap:8px;padding:4px 0 8px;border-bottom:1px solid #eef2f6}.annotation-favorites-heading strong{font-size:13px}.annotation-favorites-heading>span{margin-right:auto;font-size:11px;color:#7891a8}.annotation-favorites-heading .el-button{margin:0}
.annotation-favorites-search{display:flex;flex:none;gap:8px;padding-top:10px}.annotation-favorites-search>.el-input{min-width:0;flex:1}
.favorite-list-tools{display:flex;flex:none;gap:8px;justify-content:space-between;align-items:center;padding:7px 0}.favorite-list-tools>small{font-size:11px;color:#64748b}.favorite-list-tools>.el-button{font-size:11px;margin-left:auto}
.annotation-favorites-list{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain}
.annotation-favorites-paging{flex:none;background:#fff}.annotation-favorites-paging p{margin:0;padding:4px 0 6px;font-size:11px;color:#64748b}
.favorite-candidates{display:flex;flex:1;min-height:0;max-height:min(480px,calc(100vh - 170px));flex-direction:column;gap:8px}.favorite-candidates>.el-input{flex:none}.favorite-candidates__list{flex:1;min-height:0;overflow-y:auto}.favorite-candidate{display:flex;align-items:center;gap:10px;padding:10px 2px;border-bottom:1px solid #edf1f5}.favorite-candidate>span{display:flex;flex:1;min-width:0;flex-direction:column;gap:4px}.favorite-candidate strong{font-size:12px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.favorite-candidate small{font-size:11px;color:#7891a8}
@media(max-width:440px){.annotation-favorites-heading{flex-wrap:wrap}.favorite-tabs button{font-size:11px}.favorite-tabs small{display:block}.favorite-list-tools>small{max-width:60%}}
</style>
