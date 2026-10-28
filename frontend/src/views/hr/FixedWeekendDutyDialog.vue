<template>
  <DraggableFormDialog :model-value="modelValue" title="固定值班人员" append-to-body width="min(960px, calc(100vw - 32px))" top="5vh" :before-close="close" @update:model-value="$emit('update:modelValue',$event)">
    <p>选择固定安排周六、周日值班的人员。配置自今天起生效，历史日期保留；保存配置后，请到对应月份点击“同步”更新工作台。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <AppForm v-if="state" :model="state" label-width="80px" v-loading="loading" data-dialog-field-search-group-title="固定值班人员">
      <el-table :data="people" border size="small">
        <el-table-column prop="name" label="人员" min-width="120" />
        <el-table-column label="值班部门" min-width="180"><template #default="{row}"><el-form-item :label="`${row.name}部门`" :prop="`settings.${row.id}.department`" label-width="0"><el-select v-model="state.settings[row.id].department" :aria-label="`${row.name}值班部门`" :disabled="saving"><el-option v-for="item in departments" :key="item.code" :value="item.code" :label="item.label" /></el-select></el-form-item></template></el-table-column>
        <el-table-column label="固定值班日期" min-width="230"><template #default="{row}"><el-form-item :label="`${row.name}值班日期`" :prop="`settings.${row.id}.weekdays`" label-width="0"><el-checkbox-group v-model="state.settings[row.id].weekdays" :disabled="saving" :aria-label="`${row.name}固定值班日期`"><el-checkbox :value="5">周六</el-checkbox><el-checkbox :value="6">周日</el-checkbox></el-checkbox-group></el-form-item></template></el-table-column>
      </el-table>
    </AppForm>
    <template #footer><el-button :disabled="saving" @click="close()">关闭</el-button><el-button type="primary" :loading="saving" :disabled="loading||!ready" @click="save">保存配置</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {getFixedWeekendDuty,saveFixedWeekendDuty} from '@/api/monthlyShifts'
const props=defineProps({modelValue:Boolean}),emit=defineEmits(['update:modelValue','saved'])
const state=ref(null),people=ref([]),departments=ref([]),revision=ref(0),loading=ref(false),saving=ref(false),ready=ref(false),error=ref('')
let sequence=0
watch(()=>props.modelValue,async value=>{const id=++sequence;if(!value)return;loading.value=true;error.value='';state.value=null;ready.value=false;try{const data=await getFixedWeekendDuty();if(id!==sequence)return;people.value=data.people;departments.value=data.departments;revision.value=data.revision;ready.value=data.ready;const saved=new Map(data.assignments.map(row=>[row.user_id,row]));state.value={id:`fixed-duty:${data.revision}`,settings:Object.fromEntries(data.people.map(person=>[person.id,{department:saved.get(person.id)?.department||person.default_department||data.departments[0]?.code,weekdays:[...(saved.get(person.id)?.weekdays||[])]}]))}}catch(e){if(id===sequence)error.value=e.detail||'加载固定值班人员失败'}finally{if(id===sequence)loading.value=false}})
function close(done){if(saving.value)return;if(typeof done==='function')done();else emit('update:modelValue',false)}
async function save(){const assignments=people.value.flatMap(person=>{const row=state.value.settings[person.id];return row.weekdays.length?[{user_id:person.id,department:row.department,weekdays:row.weekdays}]:[]});saving.value=true;error.value='';try{await saveFixedWeekendDuty({revision:revision.value,assignments});ElMessage.success('固定值班配置已保存，点击对应月份同步后更新工作台');emit('saved');emit('update:modelValue',false)}catch(e){error.value=e.detail||'保存失败，请重新打开后重试'}finally{saving.value=false}}
</script>
<style scoped>p{font-size:13px;line-height:1.7;color:#64748b}.el-form-item{margin:0}.el-checkbox{margin-right:16px}</style>
