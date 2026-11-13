<template>
  <el-card shadow="never">
    <template #header>
      <div class="heading">
        <strong>{{clientScope?'口译项目收费':'口译'}}</strong>
        <div class="heading-actions">
          <template v-if="canReadProjects">
            <el-button @click="quotationVisible=true">报价单</el-button>
            <el-button @click="statementVisible=true">对账单</el-button>
          </template>
          <TableColumnSettings v-model="selectedKeys" settings-key="interpretation-customer-finance" :columns="columns" @reset="resetColumns" />
        </div>
      </div>
    </template>
    <CustomerQuotationDialog v-model="quotationVisible" module="interpretation" :projects="rows" :query="queryParams()" />
    <InterpretationStatementDialog v-model="statementVisible" :projects="rows" :query="queryParams()" />
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
      <el-table-column v-if="canReadProjects" label="操作" fixed="right" width="185"><template #default="{row}"><InterpretationFinanceEditor :target-id="row.id" :can-write="canWrite" @saved="saved" /></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" layout="total, prev, pager, next" @current-change="load" />
    <el-descriptions title="当前筛选全部项目金额小计" :column="2" border><el-descriptions-item label="不含税总价">{{formatFinanceAmounts(totalsExclTax)}}</el-descriptions-item><el-descriptions-item label="含税总价">{{formatFinanceAmounts(totalsInclTax)}}</el-descriptions-item><el-descriptions-item label="原总价（税口径未确认）"><span class="finance-text">{{formatFinanceAmounts(totals)}}</span></el-descriptions-item><el-descriptions-item label="原调整总价（税口径未确认）"><span class="finance-text">{{formatFinanceAmounts(adjustedTotals)}}</span></el-descriptions-item></el-descriptions><p v-if="incomplete">{{incomplete}} 个项目尚未填写单价；小计仅包含已登记金额。</p>
  </el-card>
</template>
<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import {computed,ref,reactive,onMounted,onBeforeUnmount,onActivated,onDeactivated,watch} from 'vue'
import {getInterpretationFinancePage} from '@/api/interpretationCustomerFinance'
import InterpretationFinanceEditor from '@/components/common/InterpretationFinanceEditor.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import {useTableColumns} from '@/composables/useTableColumns'
import {formatFinanceAmounts,financeSummary} from '@/utils/interpretationCustomerFinance'
import {getProjectStatusLabel} from '@/utils/projectStatus'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import FinanceManagerNameSelect from '@/components/common/FinanceManagerNameSelect.vue'
import CustomerQuotationDialog from '@/components/common/CustomerQuotationDialog.vue'
import InterpretationStatementDialog from '@/components/common/InterpretationStatementDialog.vue'
const emit=defineEmits(['saved'])
function saved(){emit('saved');void load()}
const props=defineProps({clientId:{type:[String,Number],default:''},clientScope:Boolean})
const columns=[{key:'order_no',label:'订单号',width:180},{key:'project_name',label:'项目名称',width:220},{key:'client_short_name',label:'客户简称',width:150},{key:'project_status',label:'项目状态',width:130},{key:'directions',label:'口译方向',width:220},{key:'rates',label:'单价',width:340},{key:'totals_excl_tax',label:'不含税总价',width:170},{key:'totals_incl_tax',label:'含税总价',width:170},{key:'totals',label:'原总价（税口径未确认）',width:180},{key:'adjusted_totals',label:'调整后总价',width:160},{key:'billing_totals',label:'计费合计',width:160},{key:'explanation',label:'说明',width:220}]
const {selectedKeys,isVisible,reset:resetColumns}=useTableColumns('interpretation-customer-finance',columns,['order_no','project_name','client_short_name','project_status','directions','rates','totals_excl_tax','totals_incl_tax','billing_totals'])
const visibleColumns=computed(()=>columns.filter(col=>isVisible(col.key)))
const canWrite=hasPermission('projects:write'),selfName=localStorage.getItem('user_full_name')||localStorage.getItem('user_name')||'当前用户'
const canReadProjects=hasPermission('projects:read')||canWrite
const quotationVisible=ref(false),statementVisible=ref(false)
const totalsExclTax=ref({}),totalsInclTax=ref({})
const filters=reactive({keyword:'',manager:props.clientScope?'all':'self',managerName:''}),rows=ref([]),totals=ref({}),adjustedTotals=ref({}),incomplete=ref(0),page=ref(1),total=ref(0),loading=ref(false),error=ref('')
let sequence=0,controller,timer
let activated=false
function queryParams(){return {client_id:props.clientId||undefined,only_mine:filters.manager==='self',client_manager:filters.manager==='name'?filters.managerName:undefined}}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await getInterpretationFinancePage({...queryParams(),keyword:filters.keyword,skip:(page.value-1)*10,limit:10},controller.signal);if(seq===sequence){totalsExclTax.value=data.totals_excl_tax||{};totalsInclTax.value=data.totals_incl_tax||{};rows.value=data.items;total.value=data.total;totals.value=data.totals;adjustedTotals.value=data.adjusted_totals;incomplete.value=data.incomplete}}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'口译财务加载失败')}finally{if(seq===sequence)loading.value=false}}
function search(){clearTimeout(timer);page.value=1;void load()}
function queueSearch(){clearTimeout(timer);controller?.abort();sequence++;if(!filters.keyword.trim())search();else timer=setTimeout(search,400)}
function reset(){filters.keyword='';filters.manager=props.clientScope?'all':'self';filters.managerName='';search()}
function cell(row,key){if(key==='project_status')return getProjectStatusLabel('interpretation',row[key]);if(key==='directions')return row.directions.map(x=>x.label).join('\n')||'-';if(key==='rates')return financeSummary({...row.payload,has_overtime:false,adjusted_totals:[],explanation:''});if(['totals','adjusted_totals','totals_excl_tax','totals_incl_tax','billing_totals'].includes(key))return formatFinanceAmounts(row[key]);if(key==='explanation')return row.payload.explanation||'-';return row[key]||'-'}
onMounted(()=>void load())
onActivated(()=>{if(activated)void load();activated=true})
watch(()=>props.clientId,search)
onBeforeUnmount(()=>{sequence++;clearTimeout(timer);controller?.abort()})
onDeactivated(()=>{quotationVisible.value=false;statementVisible.value=false})
useProjectStatusSync('interpretation',rows,{field:'project_status',onChanged:()=>{if(!loading.value)void load()}})
</script>
<style scoped>
.heading,.heading-actions{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}.heading-actions>.el-button{margin:0}.finance-text{white-space:pre-wrap;overflow-wrap:anywhere}.finance-detail{max-height:560px;overflow-y:auto}.el-pagination{margin:16px 0}.el-select{width:220px}p{font-size:12px;color:#64748b}
</style>
