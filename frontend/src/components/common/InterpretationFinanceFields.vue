<template>
  <div>
    <p v-if="referenceOnly">同一口译方向可添加多行，分别登记月、周、天、半天、小时的客户参考单价。</p><p v-else>同一口译方向可添加多行，组合月、周、天、半天、小时；金额按单价 × 数量累计，币种分别统计。</p>
    <section v-for="(rate,index) in model.rates" :key="index" class="rate-row" data-dialog-field-search-group :data-dialog-field-search-group-title="`口译单价 ${index+1}`">
      <el-form-item label="口译方向" :prop="`rates.${index}.direction`" :rules="[{validator:(_rule,value,done)=>done(!value||(!referenceOnly&&!directions.some(item=>item.label===value))?new Error('请选择项目中的口译方向'):undefined),trigger:'change'}]">
        <LanguagePairSelect v-if="referenceOnly" :model-value="rate.direction.replace(/\s*↔\s*/g,'→')" single :allow-create="false" :show-hint="false" placeholder="请选择系统语言对" @update:model-value="rate.direction=$event.replace(/→/g,' ↔ ')" />
        <el-select v-else v-model="rate.direction" filterable default-first-option><el-option v-for="item in directionOptions" :key="item" :label="item" :value="item" /></el-select>
      </el-form-item>
      <p v-if="!taxPriceSummary(rate.taxPrices) && rate.amount!=null">原单价（税口径未确认）：{{rate.amount}}</p>
      <TaxPriceFields v-model="rate.taxPrices" :prefix="`rates.${index}.taxPrices`" :show-totals="!referenceOnly" @change="value=>rate.amount=taxUnitAmount(value,rate.amount)" />
      <el-form-item label="原单价（税口径未确认）" :prop="`rates.${index}.amount`" :rules="[{required:true,message:'请填写单价',trigger:'change'}]">
        <el-input-number v-model="rate.amount" :min="0" :precision="6" :controls="false" />
      </el-form-item>
      <el-form-item label="货币" :prop="`rates.${index}.currency`" :rules="[{required:true,pattern:/^[A-Z]{3}$/,message:'填写三位大写货币代码',trigger:'change'}]"><el-select v-model="rate.currency" filterable allow-create><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item>
      <el-form-item label="单位"><el-select v-model="rate.unit" @change="unitChanged(rate)"><el-option v-for="unit in ['月','周','天','半天','小时']" :key="unit" :value="unit" /></el-select></el-form-item>
      <el-form-item v-if="!referenceOnly" label="数量" :prop="`rates.${index}.quantity`" :rules="[{required:true,message:'请填写数量',trigger:'change'}]"><el-input-number v-model="rate.quantity" :min="0" :max="999999" :precision="4" :controls="false" /></el-form-item>
      <el-form-item v-if="['天','半天'].includes(rate.unit)" label="每单位小时数" :prop="`rates.${index}.hours`" :rules="[{required:true,message:'请填写小时数',trigger:'change'}]"><el-input-number v-model="rate.hours" :min="0.0001" :max="744" :precision="4" :controls="false" /><el-checkbox v-if="rate.unit==='天'" v-model="rate.includes_lunch">含中午/午餐时间</el-checkbox></el-form-item>
      <el-button type="danger" link @click="model.rates.splice(index,1)">移除此项</el-button>
    </section>
    <el-button :disabled="!referenceOnly&&!directions.length" @click="addRate">添加组合单价</el-button>
    <p v-if="!referenceOnly&&!directions.length">请先在项目表单选择完整的口译方向。</p>
    <template v-if="!referenceOnly">
      <el-form-item label="加班费"><el-checkbox v-model="model.has_overtime">有加班费</el-checkbox></el-form-item>
      <div v-if="model.has_overtime" class="money-row"><TaxPriceFields v-model="model.overtime.taxPrices" prefix="overtime.taxPrices" :show-unit-prices="false" @change="value=>model.overtime.amount=value.totalExclTax??value.totalInclTax??model.overtime.amount" /><el-form-item label="原加班费（税口径未确认）" prop="overtime.amount" :rules="[{required:true,message:'请填写总加班费'}]"><el-input-number v-model="model.overtime.amount" :min="0" :precision="2" :controls="false" /></el-form-item><el-form-item label="加班费货币"><el-select v-model="model.overtime.currency"><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item></div>
      <p>总价包含加班费。调整后总价为空时采用计算总价，填写后视为含加班费的最终金额。</p>
      <div v-for="(row,index) in model.adjusted_totals" :key="index" class="money-row"><TaxPriceFields v-model="row.taxPrices" :prefix="`adjusted_totals.${index}.taxPrices`" :show-unit-prices="false" @change="value=>row.amount=value.totalExclTax??value.totalInclTax??row.amount" /><el-form-item label="原调整总价（税口径未确认）" :prop="`adjusted_totals.${index}.amount`" :rules="[{required:true,message:'请填写调整金额'}]"><el-input-number v-model="row.amount" :min="0" :precision="2" :controls="false" /></el-form-item><el-form-item label="调整货币"><el-select v-model="row.currency"><el-option v-for="code in currencies" :key="code" :value="code" /></el-select></el-form-item><el-button link type="danger" @click="model.adjusted_totals.splice(index,1)">取消调整</el-button></div>
      <el-button @click="model.adjusted_totals.push({amount:undefined,currency:'CNY'})">添加总价调整</el-button>
    </template>
    <el-form-item :label="referenceOnly?'说明':'内部说明'"><el-input v-model="model.explanation" type="textarea" :rows="3" maxlength="5000" show-word-limit /></el-form-item>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import TaxPriceFields from './TaxPriceFields.vue'
import {taxPriceForm,taxUnitAmount,taxPriceSummary} from '@/utils/taxPrices'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
const model=defineModel({type:Object,required:true})
const props=defineProps({directions:{type:Array,default:()=>[]},referenceOnly:Boolean})
const currencies=['CNY','USD','EUR','HKD','GBP','JPY','KRW','AUD','CAD','SGD']
const directionOptions=computed(()=>[...new Set(props.directions.map(x=>x.label))])
function addRate(){model.value.rates.push({direction:props.directions[0]?.label||'',amount:undefined,currency:'CNY',taxPrices:taxPriceForm(),unit:'天',quantity:1,hours:8,includes_lunch:false})}
function unitChanged(row){row.hours=row.unit==='天'?8:row.unit==='半天'?3:null;if(row.unit!=='天')row.includes_lunch=false}
</script>
<style scoped>
p{font-size:12px;color:#64748b}.rate-row{display:flex;flex-wrap:wrap;gap:10px;border:1px solid #e2e8f0;border-radius:6px;padding:12px;margin:12px 0}.rate-row .el-form-item{width:170px}.rate-row .el-form-item:first-child{width:280px}.el-select,.el-input-number{width:100%}.money-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px}.money-row .el-select{width:130px}
</style>
