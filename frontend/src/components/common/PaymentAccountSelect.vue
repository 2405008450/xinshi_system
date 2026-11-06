<template>
  <el-select :model-value="modelValue" filterable clearable placeholder="请选择付款账户" style="width:100%" @update:model-value="select">
    <el-option v-for="name in options" :key="name" :label="name" :value="name" />
    <el-option label="自定义添加" value="__add_payment_account__" />
  </el-select>
</template>
<script setup>
import {computed,ref} from 'vue'
import {ElMessageBox} from 'element-plus'
const props=defineProps({modelValue:{type:String,default:''}})
const emit=defineEmits(['update:modelValue'])
const defaults=['广州公司公账','深圳公司公账','上海公司公账','赵震锋招行','赵震锋工行','赵震锋农行','赵震锋中行','LULU微信','店铺公司微信','公司（赵震锋）支付宝','现金']
const key=`payment-account-options:${localStorage.getItem('user_id')||'anonymous'}`
let stored=[]
try{const data=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(data))stored=data.filter(value=>typeof value==='string'&&value.trim()&&value.length<=50&&value!=='__add_payment_account__')}catch{/* 无效配置使用预置选项。 */}
const custom=ref(stored)
const options=computed(()=>[...new Set([...defaults,...custom.value,...(props.modelValue?[props.modelValue]:[])])])
async function select(value){
  if(value!=='__add_payment_account__'){emit('update:modelValue',value||'');return}
  try{
    const result=await ElMessageBox.prompt('请输入付款账户名称（最多50字）','自定义添加',{confirmButtonText:'添加并选用',cancelButtonText:'取消',inputValidator:value=>!!value?.trim()&&value.trim().length<=50&&value.trim()!=='__add_payment_account__'||'请输入1～50字的付款账户名称'})
    const name=result.value.trim();custom.value=[...new Set([...custom.value,name])]
    try{localStorage.setItem(key,JSON.stringify(custom.value))}catch{/* 当前记录仍由业务接口保存。 */}
    emit('update:modelValue',name)
  }catch{/* 取消时保留原有选择。 */}
}
</script>
