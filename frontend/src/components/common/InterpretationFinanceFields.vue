<template>
  <div>
    <p>同一口译方向可添加多行，组合月、周、天、半天、小时；金额按单价 × 数量累计，币种分别统计。</p>
    <section v-for="(rate,index) in model.rates" :key="index" class="rate-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`口译单价 ${index+1}`">
      <el-form-item label="口译方向" :prop="`rates.${index}.direction`" :rules="[{required:true,message:'请选择口译方向',trigger:'change'}]">
        <el-select v-model="rate.direction" filterable :allow-create="!directions.length" default-first-option><el-option v-for="item in directionOptions" :key="item" :label="item" :value="item" /></el-select>
      </el-form-item>
      <el-form-item label="单价金额" :prop="`rates.${index}.amount`" :rules="[{required:true,message:'请填写金额',trigger:'change'}]"><el-input-number v-model="rate.amount" :min="0" :max="9999999999" :precision="4" :controls="false" /></el-form-item>
      <el-form-item label="货币" :prop="`rates.${index}.currency`" :rules="[{required:true,pattern:/^[A-Z]{3}$/,message:'填写三位大写货币代码',trigger:'change'}]"><el-select v-model="rate.currency" filterable allow-create><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item>
      <el-form-item label="单位"><el-select v-model="rate.unit" @change="unitChanged(rate)"><el-option v-for="unit in ['月','周','天','半天','小时']" :key="unit" :value="unit" /></el-select></el-form-item>
      <el-form-item label="数量" :prop="`rates.${index}.quantity`" :rules="[{required:true,message:'请填写数量',trigger:'change'}]"><el-input-number v-model="rate.quantity" :min="0" :max="999999" :precision="4" :controls="false" /></el-form-item>
      <el-form-item v-if="['天','半天'].includes(rate.unit)" label="每单位小时数" :prop="`rates.${index}.hours`" :rules="[{required:true,message:'请填写小时数',trigger:'change'}]"><el-input-number v-model="rate.hours" :min="0.0001" :max="744" :precision="4" :controls="false" /><el-checkbox v-if="rate.unit==='天'" v-model="rate.includes_lunch">含中午/午餐时间</el-checkbox></el-form-item>
      <el-button type="danger" link @click="model.rates.splice(index,1)">移除此项</el-button>
    </section>
    <el-button @click="addRate">添加组合单价</el-button>
    <template v-if="!referenceOnly">
      <el-form-item label="加班费"><el-checkbox v-model="model.has_overtime">有加班费</el-checkbox></el-form-item>
      <div v-if="model.has_overtime" class="money-row"><el-form-item label="总加班费" prop="overtime.amount" :rules="[{required:true,message:'请填写总加班费'}]"><el-input-number v-model="model.overtime.amount" :min="0" :precision="2" :controls="false" /></el-form-item><el-form-item label="加班费货币"><el-select v-model="model.overtime.currency"><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item></div>
      <p>总价包含加班费。调整后总价为空时采用计算总价，填写后视为含加班费的最终金额。</p>
      <div v-for="(row,index) in model.adjusted_totals" :key="index" class="money-row"><el-form-item label="调整后总价" :prop="`adjusted_totals.${index}.amount`" :rules="[{required:true,message:'请填写调整金额'}]"><el-input-number v-model="row.amount" :min="0" :precision="2" :controls="false" /></el-form-item><el-form-item label="调整货币"><el-select v-model="row.currency"><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item><el-button link type="danger" @click="model.adjusted_totals.splice(index,1)">取消调整</el-button></div>
      <el-button @click="model.adjusted_totals.push({amount:undefined,currency:'CNY'})">添加总价调整</el-button>
    </template>
    <el-form-item label="说明"><el-input v-model="model.explanation" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item>
  </div>
</template>
<script setup>
import {computed} from 'vue'
const model=defineModel({type:Object,required:true})
const props=defineProps({directions:{type:Array,default:()=>[]},referenceOnly:Boolean})
const currencies=['CNY','USD','EUR','HKD','GBP','JPY','KRW','AUD','CAD','SGD']
const directionOptions=computed(()=>[...new Set([...props.directions.map(x=>x.label),...model.value.rates.map(x=>x.direction).filter(Boolean)])])
function addRate(){model.value.rates.push({direction:props.directions[0]?.label||'',amount:undefined,currency:'CNY',unit:'天',quantity:1,hours:8,includes_lunch:false})}
function unitChanged(row){row.hours=row.unit==='天'?8:row.unit==='半天'?3:null;if(row.unit!=='天')row.includes_lunch=false}
</script>
<style scoped>
p{font-size:12px;color:#64748b}.rate-row{display:flex;flex-wrap:wrap;gap:10px;border:1px solid #e2e8f0;border-radius:6px;padding:12px;margin:12px 0}.rate-row .el-form-item{width:170px}.rate-row .el-form-item:first-child{width:280px}.el-select,.el-input-number{width:100%}.money-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px}.money-row .el-select{width:130px}
</style>
