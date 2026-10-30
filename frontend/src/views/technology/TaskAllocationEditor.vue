<template>
  <DraggableFormDialog :model-value="true" title="执行人分工" width="min(1000px, calc(100vw - 32px))" top="5vh" class="task-allocation-dialog" append-to-body :close-on-click-modal="false" :before-close="cancel">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="执行人分工" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body"><p>分别填写每人的具体分工和预定完成时间。完成日期、按时情况、奖励及抵消奖金将分别记录。</p>
      <el-select v-model="ids" multiple filterable placeholder="选择执行人" aria-label="分工执行人" @change="sync"><el-option v-for="person in people" :key="person.id" :value="person.id" :label="person.name" /></el-select>
      <AppForm ref="form" :model="model" label-position="top">
        <section v-for="(item,index) in model.items" :key="item.executor_id" data-dialog-field-search-group class="allocation-person"><h4 data-dialog-field-search-group-title>{{ name(item.executor_id) }}</h4>
          <el-form-item label="具体分工" :prop="`items.${index}.content`" :rules="[{ required:true, whitespace:true, message:'请填写该执行人的分工', trigger:'blur' }]"><el-input v-model="item.content" type="textarea" :rows="3" maxlength="100000" :aria-label="`${name(item.executor_id)}的具体分工`" /></el-form-item>
          <el-form-item label="预定完成时间" :prop="`items.${index}.due_at`" :rules="item.completed_on ? [{required:true,message:'已完成的分工不能清空预定完成时间',trigger:'change'}] : []"><el-date-picker v-model="item.due_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" :automatic-dropdown="false" :aria-label="`${name(item.executor_id)}的预定完成时间`" /></el-form-item>
        </section>
      </AppForm>
    </div>
    <template #footer><el-button @click="cancel">取消</el-button><el-button type="primary" :disabled="!model.items.length" @click="confirm">确定分工</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { reactive, ref } from 'vue'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
const props=defineProps({ people:{type:Array,required:true}, selected:{type:Array,required:true}, allocations:{type:Array,default:()=>[]}, defaultDue:{type:String,default:''} }),emit=defineEmits(['cancel','confirmed'])
const ids=ref([...props.selected]),model=reactive({items:props.allocations.map(item=>({...item}))}),form=ref(null),body=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const name=id=>props.people.find(person=>person.id===id)?.name||'原执行人'
const cache=new Map(model.items.map(item=>[item.executor_id,item]))
function sync(){for(const item of model.items)cache.set(item.executor_id,item);model.items=ids.value.map(id=>cache.get(id)||{executor_id:id,content:'',due_at:props.defaultDue})}
function cancel(){emit('cancel')}
async function confirm(){if(await form.value.validate().catch(()=>false))emit('confirmed',model.items.map(item=>({...item})))}
sync()
</script>
<style scoped>.allocation-person{margin-top:14px;border:1px solid var(--el-border-color);border-radius:6px;padding:12px}.allocation-person h4{margin:0 0 10px}.el-select{width:100%}</style>
<style>.task-allocation-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.task-allocation-dialog>.el-dialog__header,.task-allocation-dialog>.el-dialog__footer{flex-shrink:0}.task-allocation-dialog>.el-dialog__body{min-height:0;flex:1;overflow-y:auto}.task-allocation-dialog>.el-dialog__footer{border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}</style>
