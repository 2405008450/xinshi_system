<template>
  <section class="individual-scopes">
    <h4>逐人匹配查看范围</h4>
    <p>每个查看人可独立匹配不同部门和人员。启用的个人专属规则优先于多人共享规则；同一人的多个专属规则取并集。</p>
    <div class="individual-tools"><el-input v-model="keyword" clearable placeholder="搜索已设置查看人的姓名或账号" aria-label="搜索查看人" /><el-select v-model="selected" filterable clearable placeholder="搜索并添加或设置查看人" aria-label="添加或设置查看人"><el-option v-for="person in catalog.people" :key="person.id" :value="person.id" :label="`${person.name}（${person.username}）`" /></el-select><el-button type="primary" :disabled="!selected || disabled" @click="configure(selected)">设置此人范围</el-button></div>
    <el-table :data="viewers" border empty-text="暂无匹配查看人"><el-table-column label="查看人" min-width="180"><template #default="{row}">{{row.name}}（{{row.username}}）</template></el-table-column><el-table-column label="生效方式" width="120"><template #default="{row}"><el-tag :type="isPersonal(row.id)?'success':'info'">{{isPersonal(row.id)?'个人专属':'共享范围'}}</el-tag></template></el-table-column><el-table-column label="可查看范围" min-width="320"><template #default="{row}">{{summary(row.id)}}</template></el-table-column><el-table-column label="匹配人数" width="100"><template #default="{row}">{{matched(row.id).length}} 人</template></el-table-column><el-table-column label="操作" width="110" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="disabled" @click="configure(row.id)">设置范围</el-button></template></el-table-column></el-table>
  </section>
</template>
<script setup>
import {computed,ref} from 'vue'
import {matchesSearchFields} from '@/utils/searchMatching'
import {reportScopePeople} from '@/utils/workReportAccess'
const props=defineProps({catalog:{type:Object,required:true},disabled:Boolean}),emit=defineEmits(['configure'])
const keyword=ref(''),selected=ref('')
const relevant=id=>props.catalog.rules.filter(rule=>rule.enabled&&(rule.viewers_all||rule.viewer_ids.includes(id)))
const personal=id=>relevant(id).filter(rule=>!rule.viewers_all&&rule.viewer_ids.filter(value=>id===props.catalog.configurator_id||value!==props.catalog.configurator_id).length===1)
const effective=id=>personal(id).length?personal(id):relevant(id)
const isPersonal=id=>personal(id).length>0
const viewers=computed(()=>props.catalog.people.filter(person=>relevant(person.id).length&&matchesSearchFields([person.name,person.username],keyword.value)))
function combined(id){const rows=effective(id);return {senders_all:rows.some(row=>row.senders_all),all_departments:rows.some(row=>row.all_departments),department_ids:[...new Set(rows.flatMap(row=>row.department_ids))],sender_ids:[...new Set(rows.flatMap(row=>row.sender_ids))]}}
function matched(id){return reportScopePeople(combined(id),props.catalog.people)}
function summary(id){const scope=combined(id);if(scope.senders_all)return '全体人员（包括未分配部门人员）';return [scope.all_departments?'全部部门':scope.department_ids.map(id=>props.catalog.departments.find(item=>item.id===id)?.name||'已移除部门').join('、'),scope.sender_ids.map(id=>props.catalog.people.find(item=>item.id===id)?.name||'已停用人员').join('、')].filter(Boolean).join('；')||'尚未设置'}
function configure(id){const person=props.catalog.people.find(row=>row.id===id);if(!person)return;const row=personal(id)[0];emit('configure',{person,row,scope:combined(id)})}
</script>
<style scoped>.individual-scopes{display:flex;flex-direction:column;gap:12px}.individual-scopes h4,.individual-scopes p{margin:0}.individual-scopes p{font-size:13px;color:#64748b}.individual-tools{display:flex;gap:12px;flex-wrap:wrap}.individual-tools>.el-input,.individual-tools>.el-select{width:300px;max-width:100%}</style>
