<template>
  <div class="existing-client-autocomplete">
    <el-autocomplete v-bind="$attrs" :model-value="query" :fetch-suggestions="fetchSuggestions" :value-key="valueKey" :debounce="400" :trigger-on-focus="true" clearable :placeholder="placeholder" style="width:100%" @update:model-value="input" @select="select" @clear="clear" @focus="focused=true" @blur="checkSelection">
      <template v-if="$slots.default" #default="scope"><slot v-bind="scope" /></template>
    </el-autocomplete>
    <small v-if="rejected" class="existing-client-guidance" role="status">{{guidance}}</small>
  </div>
</template>
<script setup>
import {onBeforeUnmount,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
defineOptions({inheritAttrs:false})
const props=defineProps({modelValue:{type:String,default:''},fetchSuggestions:{type:Function,required:true},valueKey:{type:String,default:'client_short_name'},placeholder:{type:String,default:'搜索并选择已有客户简称'}})
const emit=defineEmits(['update:modelValue','select','clear','input'])
const guidance='请在 新咨询管理/客户管理 先输入客户名称'
const query=ref(props.modelValue),focused=ref(false),rejected=ref(false)
let timer
function input(value){clearTimeout(timer);query.value=value;rejected.value=false;emit('update:modelValue','');emit('input',value)}
function select(item){clearTimeout(timer);query.value=item[props.valueKey]||'';rejected.value=false;emit('update:modelValue',query.value);emit('select',item)}
function clear(){clearTimeout(timer);query.value='';rejected.value=false;emit('update:modelValue','');emit('clear')}
function checkSelection(){focused.value=false;clearTimeout(timer);const attempted=query.value;timer=setTimeout(()=>{if(attempted&&attempted!==props.modelValue){rejected.value=true;query.value=props.modelValue;ElMessage.warning(guidance)}},150)}
watch(()=>props.modelValue,value=>{if(value||!focused.value)query.value=value||''})
onBeforeUnmount(()=>clearTimeout(timer))
</script>
<style scoped>.existing-client-autocomplete{width:100%}.existing-client-guidance{display:block;color:var(--el-color-danger);line-height:1.6;margin-top:4px}</style>
