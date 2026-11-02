<template>
  <el-card shadow="never">
    <template #header><div class="heading"><strong>财务管理（客户）</strong><TableColumnSettings v-model="selectedKeys" settings-key="interpretation-customer-finance" :columns="columns" @reset="resetColumns" /></div></template>
    <AppForm :model="filters" inline @submit.prevent="search">
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="订单号、项目名称、客户名称" clearable @input="queueSearch" @keyup.enter="search" /></el-form-item>
      <el-form-item label="客户经理"><el-select v-model="filters.manager" placeholder="选择或输入客户经理" @change="search"><el-option :label="`本人（${selfName}）`" value="self" /><el-option label="全部客户经理" value="all" /><el-option label="指定客户经理" value="name" /></el-select><FinanceManagerNameSelect v-if="filters.manager==='name'" v-model="filters.managerName" @change="search" /></el-form-item>
      <el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" border row-key="id">
      <el-table-column type="index" label="序号" width="65" :index="index=>(page-1)*10+index+1" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :label="column.label" :min-width="column.width"><template #default="{row}"><span class="finance-text">{{cell(row,column.key)}}</span></template></el-table-column>
      <el-table-column label="详情" fixed="right" width="100"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" title="口译客户财务详情"><template #reference><el-button link type="primary">查看详情</el-button></template><div class="finance-detail"><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="column in columns" :key="column.key" :label="column.label"><span class="finance-text">{{cell(row,column.key)}}</span></el-descriptions-item></el-descriptions></div></el-popover></template></el-table-column>
      <el-table-column label="操作" fixed="right" width="185"><template #default="{row}"><InterpretationFinanceEditor :target-id="row.id" :can-write="canWrite" @saved="saved" /></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <el-descriptions title="当前筛选全部项目金额小计" :column="2" border><el-descriptions-item label="总价"><span class="finance-text">{{formatFinanceAmounts(totals)}}</span></el-descriptions-item><el-descriptions-item label="调整后总价"><span class="finance-text">{{formatFinanceAmounts(adjustedTotals)}}</span></el-descriptions-item></el-descriptions><p v-if="incomplete">{{incomplete}} 个项目尚未填写单价；小计仅包含已登记金额。</p>
  </el-card>
</template>
<script setup>
import {computed,ref,reactive,onMounted,onBeforeUnmount,watch} from 'vue'
import {getInterpretationFinancePage} from '@/api/interpretationCustomerFinance'
import InterpretationFinanceEditor from '@/components/common/InterpretationFinanceEditor.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import {useTableColumns} from '@/composables/useTableColumns'
import {formatFinanceAmounts,financeSummary} from '@/utils/interpretationCustomerFinance'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import FinanceManagerNameSelect from '@/components/common/FinanceManagerNameSelect.vue'
const emit=defineEmits(['saved'])
function saved(){emit('saved');void load()}
const props=defineProps({clientId:{type:[String,Number],default:''}})
const columns=[{key:'order_no',label:'订单号',width:180},{key:'project_name',label:'项目名称',width:220},{key:'client_short_name',label:'客户简称',width:150},{key:'project_status',label:'项目状态',width:130},{key:'directions',label:'口译方向',width:220},{key:'rates',label:'单价',width:340},{key:'totals',label:'总价',width:160},{key:'adjusted_totals',label:'调整后总价',width:160},{key:'explanation',label:'说明',width:220}]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('interpretation-customer-finance',columns,['order_no','project_name','client_short_name','project_status','directions','rates','totals','adjusted_totals'])
const visibleColumns=computed(()=>columns.filter(col=>isVisible(col.key)))
const canWrite=hasPermission('projects:write'),selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const filters=reactive({keyword:'',manager:'self',managerName:''}),rows=ref([]),totals=ref({}),adjustedTotals=ref({}),incomplete=ref(0),page=ref(1),total=ref(0),loading=ref(false),error=ref('')
let sequence=0,controller,timer
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getInterpretationFinancePage({client_id:props.clientId||undefined,keyword:filters.keyword,only_mine:filters.manager==='self',client_manager:filters.manager==='name'?filters.managerName:undefined,skip:(page.value-1)*10,limit:10},controller.signal);if(seq===sequence){rows.value=data.items;total.value=data.total;totals.value=data.totals;adjustedTotals.value=data.adjusted_totals;incomplete.value=data.incomplete}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'口译财务加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function reset(){filters.keyword='';filters.manager='self';filters.managerName='';search()}
function cell(row,key){if(key==='project_status')return getProjectStatusLabel('interpretation',row[key]);if(key==='directions')return row.directions.map(x=>x.label).join('\n')||'-';if(key==='rates')return financeSummary({...row.payload,has_overtime:false,adjusted_totals:[],explanation:''});if(['totals','adjusted_totals'].includes(key))return formatFinanceAmounts(row[key]);if(key==='explanation')return row.payload.explanation||'-';return row[key]||'-'}
onMounted(()=>void load())
watch(()=>props.clientId,search)
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
</script>
<style scoped>
.heading{display:flex;justify-content:space-between;align-items:center}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}.finance-detail{max-height:560px;overflow-y:auto}.el-pagination{margin:16px 0}.el-select{width:220px}p{font-size:12px;color:#64748b}
</style>
