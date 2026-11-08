<template>
  <div class="contact-names-editor">
    <section v-for="(row, index) in names" :key="index" class="contact-person-card" data-dialog-field-search-group :data-dialog-field-search-group-title="`客户联系人${index+1}`">
      <div class="contact-person-heading"><strong>客户联系人 {{index+1}}</strong><el-button v-if="names.length>1" link type="danger" :aria-label="`移除联系人${index+1}`" @click="remove(index)">移除</el-button></div>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="联系人" :prop="['contact_people',index,'name']" :rules="nameRules(row)"><el-input :model-value="row.name" maxlength="100" placeholder="请输入联系人姓名" :aria-label="`客户联系人${index+1}`" @update:model-value="value=>update(index,'name',value)" /></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="联系方式" :prop="['contact_people',index,'contact_method']"><el-input :model-value="row.contact_method" maxlength="5000" placeholder="电话、邮箱、微信等" :aria-label="`联系人${index+1}联系方式`" @update:model-value="value=>update(index,'contact_method',value)" /></el-form-item></el-col>
      </el-row>
      <el-form-item label="说明" :prop="['contact_people',index,'description']"><el-input :model-value="row.description" type="textarea" :rows="2" maxlength="5000" :aria-label="`联系人${index+1}说明`" placeholder="填写职务、联系偏好或其他说明" @update:model-value="value=>update(index,'description',value)" /></el-form-item>
    </section>
    <el-button link type="primary" @click="add">添加客户联系人</el-button>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props=defineProps({modelValue:{type:Array,default:()=>[]},required:{type:Boolean,default:true}})
const emit=defineEmits(['update:modelValue'])
const nameRules=row=>[
  {required:props.required || names.value.length>1 || Boolean(row.contact_method?.trim() || row.description?.trim()),whitespace:true,message:'请填写联系人姓名',trigger:['blur','change']},
  {validator:(_rule,value,done)=>{const key=String(value||'').trim().toLowerCase();done(key&&names.value.filter(item=>String(item.name||'').trim().toLowerCase()===key).length>1?new Error('联系人姓名不能重复'):undefined)},trigger:['blur','change']},
]
const blank=()=>({name:'',contact_method:'',description:''})
const names=computed(()=>props.modelValue.length?props.modelValue:[blank()])
function update(index,key,value){const next=names.value.map(row=>({...row}));next[index][key]=value;emit('update:modelValue',next)}
function add(){emit('update:modelValue',[...names.value.map(row=>({...row})),blank()])}
function remove(index){emit('update:modelValue',names.value.filter((_,item)=>item!==index))}
</script>
<style scoped>.contact-names-editor{width:100%;display:grid;gap:12px}.contact-person-card{padding:14px 16px 0;border:1px solid var(--el-border-color-lighter);border-radius:8px;min-width:0}.contact-person-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.contact-names-editor>.el-button{justify-self:start}.contact-person-card :deep(.el-form-item__label){white-space:nowrap}</style>
