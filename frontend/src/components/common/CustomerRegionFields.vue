<template>
  <el-row :gutter="20">
    <el-col v-for="field in fields" :key="field.key" :xs="24" :md="12">
      <el-form-item :label="field.label" :prop="field.key">
        <el-select :model-value="modelValue[field.key]" filterable remote allow-create default-first-option clearable :remote-method="q=>search(field.key,q)" :loading="states[field.key].loading" placeholder="选择或搜索任意国家、省市、区县" style="width:100%" @visible-change="v=>v&&search(field.key,'')" @change="value=>choose(field.key,value)">
          <el-option v-if="modelValue[field.key]" :value="modelValue[field.key]" :label="modelValue[field.key]" />
          <el-option v-for="row in states[field.key].items" :key="row.id" :value="row.id" :label="row.label" />
          <template #footer><el-button v-if="states[field.key].items.length<states[field.key].total" link :loading="states[field.key].loading" @click="search(field.key,states[field.key].query,true)">加载更多（{{states[field.key].items.length}} / {{states[field.key].total}}）</el-button><small v-if="states[field.key].error">{{states[field.key].error}}</small></template>
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  <el-form-item label="详细地址" prop="detailed_address"><el-input :model-value="modelValue.detailed_address" type="textarea" :rows="2" maxlength="5000" placeholder="手工填写街道、门牌号、楼层、房间等" @update:model-value="detail" /></el-form-item>
  <el-form-item label="完整地址" prop="full_address"><el-input :model-value="modelValue.full_address" type="textarea" :rows="3" maxlength="5000" placeholder="国家、省份、城市、区县和详细地址合并后自动同步，也可直接编辑" @update:model-value="value=>emit('update:modelValue',{...modelValue,full_address:value})" /></el-form-item>
  <p style="font-size:11px;color:var(--el-text-color-secondary)">地区参考：<a href="https://github.com/dr5hn/countries-states-cities-database" target="_blank" rel="noopener noreferrer">CSC（ODbL）</a> / <a href="https://github.com/modood/Administrative-divisions-of-China" target="_blank" rel="noopener noreferrer">中国行政区划</a>；目录未覆盖的地区可手工填写。</p>
</template>
<script setup>
import {reactive,onBeforeUnmount} from 'vue'
import api from '@/api'
const props=defineProps({modelValue:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue'])
const fields=[{key:'country',label:'国家'},{key:'province',label:'省份'},{key:'city',label:'地级市'},{key:'district',label:'区县'}]
const states=reactive(Object.fromEntries(fields.map(f=>[f.key,{items:[],query:'',total:0,loading:false,error:'',sequence:0}])))
const controllers={},timers={}
function search(key,q,more=false){clearTimeout(timers[key]);controllers[key]?.abort();const state=states[key],seq=++state.sequence;state.query=q;state.error='';const run=async()=>{controllers[key]=new AbortController();state.loading=true;try{const data=await api.get('/geography/search',{params:{q,level:key,country:props.modelValue.country,province:props.modelValue.province,city:props.modelValue.city,skip:more?state.items.length:0,limit:100},signal:controllers[key].signal});if(seq===state.sequence){state.items=more?[...state.items,...data.items]:data.items;state.total=data.total}}catch(e){if(seq===state.sequence&&e.code!=='ERR_CANCELED')state.error='地区加载失败，可重新打开或手工填写'}finally{if(seq===state.sequence)state.loading=false}};if(q&&!more)timers[key]=setTimeout(run,400);else void run()}
const merge=value=>[...fields.map(f=>value[f.key]),value.detailed_address].filter(v=>v&&String(v).trim()).map(v=>String(v).trim()).join(' ')
function detail(value){const next={...props.modelValue,detailed_address:value};next.full_address=merge(next);emit('update:modelValue',next)}
function choose(key,value){const row=states[key].items.find(r=>r.id===value);const next={...props.modelValue};if(row){for(const f of fields)next[f.key]=row[f.key]||''}else{next[key]=value||'';for(const f of fields.slice(fields.findIndex(f=>f.key===key)+1))next[f.key]=''}next.full_address=merge(next);emit('update:modelValue',next)}
onBeforeUnmount(()=>{for(const f of fields){states[f.key].sequence++;clearTimeout(timers[f.key]);controllers[f.key]?.abort()}})
</script>
