<template>
  <el-card class="project-customer-finance" shadow="never">
    <template #header><div class="finance-heading"><strong>{{moduleLabel}}</strong><TableColumnSettings v-model="selectedKeys" :settings-key="`${module}-customer-finance`" :columns="columns" @reset="resetColumns" /></div></template>
    <AppForm :model="filters" inline @submit.prevent="search"><el-form-item label="关键词"><el-input v-model="filters.keyword" clearable placeholder="订单号、项目名称、客户名称" @input="queueSearch" @keyup.enter="search" /></el-form-item><el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button></el-form-item></AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" border row-key="id">
      <el-table-column type="index" label="序号" width="64" :index="index=>(page-1)*limit+index+1" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="column.width"><template #default="{row}"><span class="finance-text">{{cell(row,column.key)}}</span></template></el-table-column>
      <el-table-column label="详情" fixed="right" width="100"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" :title="`${moduleLabel}客户财务详情`"><template #reference><el-button link type="primary">查看详情</el-button></template><div class="finance-detail"><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="column in columns" :key="column.key" :label="column.label"><span class="finance-text">{{cell(row,column.key)}}</span></el-descriptions-item></el-descriptions></div></el-popover></template></el-table-column>
      <el-table-column label="操作" fixed="right" width="150"><template #default="{row}"><el-button link type="primary" @click="editor.open(row.id)">{{canWrite?'编辑财务':'查看财务'}}</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="limit" :page-sizes="[10,20,50,100]" :total="total" layout="total, sizes, prev, pager, next, jumper" @size-change="search" @current-change="load" />
    <el-descriptions title="当前筛选金额小计（按币种区分）" :column="2" border><el-descriptions-item label="不含税总价">{{formatAmounts(totalsExcl)}}</el-descriptions-item><el-descriptions-item label="含税总价">{{formatAmounts(totalsIncl)}}</el-descriptions-item></el-descriptions>
    <p v-if="missingTotals.excl_tax||missingTotals.incl_tax" class="finance-hint">未填写的对应税口径金额不参与小计，不视为零税率。</p>
    <ProjectCustomerFinanceEditor ref="editor" :module="module" @saved="load" />
  </el-card>
</template>
<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import {computed,onActivated,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {onBeforeRouteLeave,onBeforeRouteUpdate} from 'vue-router'
import AppForm from '@/components/common/AppForm.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import ProjectCustomerFinanceEditor from '@/components/common/ProjectCustomerFinanceEditor.vue'
import {useTableColumns} from '@/composables/useTableColumns'
import {getProjectCustomerFinancePage} from '@/api/projectCustomerFinance'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {taxPriceSummary} from '@/utils/taxPrices'
import {annotationProjectTypeOptions} from '@/utils/annotationCatalog'
import {settlementLabel} from '@/utils/talentSettlement'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
const props=defineProps({module:{type:String,required:true},clientId:{type:[String,Number],default:''},clientScope:Boolean})
const moduleLabel=computed(()=>props.module==='annotation'?'标注':'招聘')
const columns=[{key:'order_no',label:'订单号',width:180},{key:'project_name',label:'项目名称',width:220},{key:'client_name',label:'客户',width:150},{key:'project_status',label:'项目状态',width:150},{key:'unit_prices',label:'客户单价（按税口径）',width:300},{key:'totals_excl_tax',label:'不含税总价',width:170},{key:'totals_incl_tax',label:'含税总价',width:170}]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns(`${props.module}-customer-finance`,columns,columns.map(row=>row.key))
const visibleColumns=computed(()=>columns.filter(row=>isVisible(row.key)))
const canWrite=hasPermission('projects:write'),editor=ref(),filters=reactive({keyword:''}),rows=ref([]),total=ref(0),page=ref(1),limit=ref(10),loading=ref(false),error=ref(''),totalsExcl=ref({}),totalsIncl=ref({}),missingTotals=ref({})
let controller,sequence=0,timer,activated=false
const formatAmounts=value=>Object.entries(value||{}).map(([currency,amount])=>`${currency} ${amount}`).join('\n')||'-'
function cell(row,key){if(key==='project_status')return getProjectStatusLabel(props.module,row[key]);if(key.startsWith('totals_'))return formatAmounts(row[key]);if(key==='unit_prices')return props.module==='annotation'?(row.prices||[]).map(price=>`${settlementLabel(annotationProjectTypeOptions,price.project_type)}：${taxPriceSummary(price.tax_prices,price.currency,price.unit,false)||`原单价（税口径未确认）${price.currency} ${price.amount}/${price.unit}`}`).join('\n')||'-':taxPriceSummary(row.tax_prices,row.currency,'',false)||(row.legacy_amount!=null?`原服务费用（税口径未确认）${row.currency} ${row.legacy_amount}`:'-');return row[key]||'-'}
async function load(){controller?.abort();controller=new AbortController();const seq=++sequence;loading.value=true;error.value='';try{const data=await getProjectCustomerFinancePage(props.module,{client_id:props.clientId||undefined,keyword:filters.keyword,skip:(page.value-1)*limit.value,limit:limit.value},{signal:controller.signal});if(seq!==sequence)return;rows.value=data.items||[];total.value=data.total||0;totalsExcl.value=data.totals_excl_tax||{};totalsIncl.value=data.totals_incl_tax||{};missingTotals.value=data.missing_totals||{};const last=Math.max(1,Math.ceil(total.value/limit.value));if(page.value>last){page.value=last;await load()}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'客户财务加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function reset(){filters.keyword='';search()}
watch(()=>[props.module,props.clientId],search,{immediate:true})
onActivated(()=>{if(activated)void load();activated=true})
onBeforeRouteLeave(()=>editor.value?.guardClose()??true)
onBeforeRouteUpdate(()=>editor.value?.guardClose()??true)
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer)})
useProjectStatusSync(()=>props.module,rows,{field:'project_status',onChanged:()=>{if(!loading.value)void load()}})
</script>
<style scoped>
.finance-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}.finance-detail{max-height:560px;overflow-y:auto}.finance-hint{font-size:12px;color:var(--el-text-color-secondary)}.el-pagination{margin:16px 0;flex-wrap:wrap;gap:8px}.project-customer-finance{min-width:0}
</style>
