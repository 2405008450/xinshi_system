<template>
 <div class="interpretation-combination-rates">
  <section v-for="(group,groupIndex) in groups" :key="group.key" class="combination-rate-group" data-dialog-field-search-group :data-dialog-field-search-group-title="`组合单价 ${groupIndex+1}`">
   <div v-for="({rate,index},lineIndex) in group.rows" :key="index" class="combination-unit-row">
    <div class="combination-direction-prices">
     <el-form-item v-if="lineIndex===0" label="口译方向" :prop="`${prefix}.${index}.direction`" :rules="[{required:hasRateContent(rate),message:'请选择口译方向',trigger:'change'}]">
      <LanguagePairSelect v-if="referenceOnly" :model-value="group.direction.replace(/\s*↔\s*/g,'→')" single :show-hint="false" @update:model-value="changeDirection(group,$event.replace(/→/g,' ↔ '))"/>
      <el-select v-else :model-value="group.direction" placeholder="请选择新组合的口译方向" @update:model-value="changeDirection(group,$event)"><el-option v-for="item in directions" :key="item.label" :label="item.label" :value="item.label" :disabled="groups.some(other=>other!==group&&other.direction===item.label)"/></el-select>
     </el-form-item>
     <div v-else class="same-direction">同方向单价 {{lineIndex+1}}</div>
     <el-form-item label="不含税单价" :prop="`${prefix}.${index}.taxPrices.unitPriceExclTax`" ><el-input-number v-model="rate.taxPrices.unitPriceExclTax" :min="0" :precision="6" :controls="false" placeholder="填写不含税单价" @update:model-value="priceChanged(rate)"/></el-form-item>
     <el-form-item label="含税单价" :prop="`${prefix}.${index}.taxPrices.unitPriceInclTax`"><el-input-number v-model="rate.taxPrices.unitPriceInclTax" :min="0" :precision="6" :controls="false" placeholder="填写含税单价" @update:model-value="priceChanged(rate)"/></el-form-item>
    </div>
    <div class="combination-rate-line">
     <el-form-item label="货币"><el-select v-model="rate.currency"><el-option v-for="code in currencies" :key="code" :value="code"/></el-select></el-form-item>
     <el-form-item label="单位"><el-select v-model="rate.unit" @change="unitChanged(rate)"><el-option v-for="unit in units" :key="unit" :value="unit"/></el-select></el-form-item>
     <el-form-item v-if="!referenceOnly" label="工作量"><el-input-number v-model="rate.quantity" :min="0" :precision="4" :controls="false" @update:model-value="clearOverride(rate)"/></el-form-item>
     <el-form-item v-if="['天','半天'].includes(rate.unit)" label="每单位小时数"><el-input-number v-model="rate.hours" :min="0.0001" :max="744" :controls="false"/><el-checkbox v-if="rate.unit==='天'" v-model="rate.includes_lunch">含中午/午餐时间</el-checkbox></el-form-item>
     <el-button link type="danger" @click="remove(group,index)">移除</el-button>
    </div>
   </div>
   <InterpretationRateTotals v-if="!referenceOnly" class="combination-subtotals" :rows="group.rows.map(item=>item.rate)" title="小计" :adjustments="group.rows[0].rate.group_adjustments||[]" :totals="basis=>rateGroupTotals(group.rows.map(item=>item.rate),basis,false)" @update:adjustments="group.rows[0].rate.group_adjustments=$event"/>
   <el-button plain @click="add(group.direction)">新增不同单位单价</el-button>
  </section>
  <el-button :disabled="!canAddGroup" @click="addGroup">添加组合单价</el-button>
  <small v-if="!canAddGroup&&groups.length">请先选定新组合的方向；同一方向请使用“新增不同单位单价”。</small>
  <InterpretationRateTotals v-if="!referenceOnly&&rows.length" class="combination-grand-totals" :rows="rows" title="合计" :adjustments="rows[0].combined_adjustments||[]" :totals="basis=>combinedRateTotals(rows,basis,false)" @update:adjustments="rows[0].combined_adjustments=$event"/>
 </div>
</template>
<script setup>
import {computed} from 'vue'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import InterpretationRateTotals from './InterpretationRateTotals.vue'
import {taxPriceForm} from '@/utils/taxPrices'
import {interpretationUnits as units,interpretationCurrencies as currencies} from '@/utils/interpretationCustomerFinance'
import {groupRates,rateGroupTotals,combinedRateTotals,hasRateContent} from '@/utils/interpretationRateGroups'
const props=defineProps({modelValue:{type:Array,default:()=>[]},directions:{type:Array,default:()=>[]},referenceOnly:Boolean,prefix:{type:String,default:'rates'},defaultUnit:{type:String,default:'天'}})
const emit=defineEmits(['update:modelValue'])
const rows=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const groups=computed(()=>groupRates(rows.value))
const canAddGroup=computed(()=>!groups.value.some(group=>!group.direction)&&(props.referenceOnly||props.directions.some(direction=>!groups.value.some(group=>group.direction===direction.label))))
function clearOverride(rate){rate.taxPrices={...rate.taxPrices,totalExclTax:undefined,totalInclTax:undefined}}
function priceChanged(rate){rate.amount=rate.taxPrices.unitPriceExclTax??rate.taxPrices.unitPriceInclTax;clearOverride(rate)}
function unitChanged(rate){rate.hours=rate.unit==='天'?8:rate.unit==='半天'?3:null;if(rate.unit!=='天')rate.includes_lunch=false}
function add(direction){const used=rows.value.filter(row=>row.direction===direction).map(row=>row.unit),unit=[props.defaultUnit,...units].find(value=>!used.includes(value))||props.defaultUnit;rows.value.push({direction,amount:undefined,currency:'CNY',taxPrices:taxPriceForm(),unit,quantity:1,hours:unit==='天'?8:unit==='半天'?3:null,includes_lunch:false})}
function addGroup(){const unused=props.directions.filter(item=>!groups.value.some(group=>group.direction===item.label));add(!groups.value.length&&unused.length===1?unused[0].label:'')}
function changeDirection(group,value){if(groups.value.some(other=>other!==group&&other.direction===value))return;group.rows.forEach(({rate})=>rate.direction=value)}
function remove(group,index){const first=rows.value[0],groupFirst=group.rows[0].rate;rows.value.splice(index,1);if(rows.value.length&&first!==rows.value[0]&&first.combined_adjustments)rows.value[0].combined_adjustments=first.combined_adjustments;const remaining=rows.value.find(row=>row.direction===group.direction);if(remaining&&groupFirst!==remaining&&groupFirst.group_adjustments)remaining.group_adjustments=groupFirst.group_adjustments}
</script>
<style scoped>
.combination-rate-group{padding:14px;border:1px solid var(--el-border-color);border-radius:8px;margin:12px 0}.combination-direction-prices{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px}.combination-rate-line{display:grid;grid-template-columns:repeat(4,minmax(100px,1fr)) auto;gap:10px;align-items:start}.combination-unit-row+.combination-unit-row{border-top:1px dashed var(--el-border-color);padding-top:12px}.interpretation-combination-rates :deep(.el-input-number),.interpretation-combination-rates :deep(.el-select){width:100%}.same-direction{align-self:center;color:var(--el-text-color-secondary)}small{display:block;color:var(--el-text-color-secondary);margin-top:6px}@media(max-width:640px){.combination-direction-prices,.combination-rate-line{grid-template-columns:1fr}}
</style>
