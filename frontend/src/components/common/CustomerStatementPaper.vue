<template>
  <article class="statement-paper">
    <h2><StatementEditableCell v-if="editable" v-model="statement.company" label="公司抬头" /><template v-else>{{statement.company}}</template></h2><h3><StatementEditableCell v-if="editable" v-model="statement.title" label="对账单标题" /><template v-else>{{statementTitle(statement)}}</template></h3>
    <div v-if="editable" class="statement-meta statement-meta--editable"><span>客户：<StatementEditableCell v-model="statement.client_name" label="客户名称" /></span><span>账单月份：<StatementEditableCell v-model="statement.month" label="账单月份显示文案" /><select v-model="statement.tax_included" aria-label="金额口径标签"><option :value="false">不含税</option><option :value="true">含税</option></select></span></div>
    <div v-else class="statement-meta"><span>客户：{{statement.client_name}}</span><span>账单月份：{{statement.month}}　{{statementTaxLabel(statement)}}</span></div>
    <div class="statement-table-wrap"><table class="statement-table">
      <colgroup><col v-if="interactive" style="width:48px" /><col v-if="hasOrigin" :style="{width:columnWidth(24)}" /><col v-if="hasCustomerOrder" :style="{width:columnWidth(24)}" /><col v-for="(weight,key) in visibleColumnWeights" :key="key" :style="{width:columnWidth(weight)}" /><col v-if="interactive" style="width:48px" /></colgroup>
      <thead><tr><th v-if="interactive" class="statement-ui">选择</th><th v-if="hasOrigin">原客户</th><th v-if="hasCustomerOrder">客户单号</th><th class="statement-date">来稿日期</th><th>项目名称</th><th>翻译方向</th><th>工作量（计价方式）</th><th v-if="showUnitPrice">单价</th><th>{{showUnitPrice?'小计':'固定价格'}}</th><th>备注</th><th v-if="interactive" class="statement-ui">操作</th></tr></thead>
      <tbody>
        <tr v-for="row in statement.rows" :key="row._row_id" :draggable="interactive&&canWrite" :class="{'statement-reference':row.counted_in_total===false}" @dragstart="startTaskDrag($event,row)" @dblclick="interactive&&canEdit&&emit('edit',row)">
          <td v-if="interactive" class="statement-ui"><button v-if="canWrite" type="button" class="statement-task-handle" :aria-label="`拖动任务 ${row.order_no}`" title="拖到另一份对账单" @pointerdown.prevent.stop="emit('task-pointer',$event,row.task_ids)">⠿</button><el-checkbox :model-value="row.task_ids.every(id=>selected.includes(id))" :disabled="!canWrite" :aria-label="`选择任务 ${row.order_no}`" @change="emit('select',row.task_ids,$event)" /></td>
          <td v-if="hasOrigin">{{row.origin_client_name||statement.client_name}}</td>
          <template v-if="editable">
            <td v-if="hasCustomerOrder"><StatementEditableCell v-model="row.customer_order_no" :label="`${row.order_no} 客户单号`" /></td>
            <td><StatementEditableCell v-model="row.received_date" :label="`${row.order_no} 来稿日期`" type="date" /></td>
            <td><StatementEditableCell v-model="row.project_name" :label="`${row.order_no} 项目名称`" multiline /></td>
            <td><StatementEditableCell v-model="row.language_pair" :label="`${row.order_no} 翻译方向`" /></td>
            <td><StatementEditableCell v-if="!isFixedStatementRow(row)" v-model="row.quantity" :label="`${row.order_no} 工作量`" /><StatementEditableCell v-model="row.basis" :label="`${row.order_no} 工作量及计价方式`" multiline /></td>
            <td v-if="showUnitPrice"><template v-if="!isFixedStatementRow(row)"><StatementEditableCell v-model="row.currency" :label="`${row.order_no} 货币`" /><StatementEditableCell v-model="row.unit_price" :label="`${row.order_no} 单价`" /><span class="statement-unit-size">每 <StatementEditableCell v-model="row.unit_size" :label="`${row.order_no} 计价数量`" /> 计价</span><StatementEditableCell v-model="row.unit_label" :label="`${row.order_no} 单价口径文案`" /></template></td>
            <td><template v-if="isFixedStatementRow(row)"><StatementEditableCell v-model="row.currency" :label="`${row.order_no} 货币`" /><StatementEditableCell v-if="mixedTax" v-model="row.unit_label" :label="`${row.order_no} 金额口径`" /></template><StatementEditableCell v-model="row.subtotal" :label="`${row.order_no} ${isFixedStatementRow(row)?'固定价格':'小计'}`" /></td>
            <td><span v-if="row.counted_in_total===false">汇总参考，不重复计入合计。</span><StatementEditableCell v-model="row.remarks" :label="`${row.order_no} 备注`" multiline /></td>
          </template>
          <template v-else><td v-if="hasCustomerOrder">{{row.customer_order_no||''}}</td><td class="statement-date">{{row.received_date||'-'}}</td><td><button v-if="interactive" type="button" class="statement-order-link" :title="`编辑订单 ${row.order_no}`" @click.stop="emit('open-order',row)">{{row.project_name}}</button><template v-else>{{row.project_name}}</template></td><td>{{row.language_pair}}</td><td><template v-if="row.quantity!=null">{{row.quantity}}<br /></template>{{statementBasis(row.basis)}}</td><td v-if="showUnitPrice"><template v-if="!isFixedStatementRow(row)">{{row.unit_price==null?'-':`${row.currency} ${statementUnitPrice(row.unit_price)}`}}<small v-if="mixedTax">（{{row.unit_label}}）</small></template></td><td>{{row.subtotal==null?'待补':`${row.currency} ${row.subtotal}`}}<small v-if="mixedTax && isFixedStatementRow(row) && row.unit_label && row.subtotal!=null">（{{row.unit_label}}）</small></td><td>{{row.counted_in_total===false?'汇总参考，不重复计入合计。':''}}{{row.remarks}}</td></template>
          <td v-if="interactive" class="statement-ui"><el-button v-if="canWrite" link type="primary" :disabled="!canEdit" @click="emit('edit',row)">修改</el-button></td>
        </tr>
        <tr v-if="!statement.rows.length"><td :colspan="(interactive?8:6)+Number(showUnitPrice)+Number(hasOrigin)+Number(hasCustomerOrder)">暂无任务，可从另一份对账单拖入</td></tr>
      </tbody>
      <tfoot><tr><td class="statement-total-label" :colspan="(interactive?5:4)+Number(showUnitPrice)+Number(hasOrigin)+Number(hasCustomerOrder)"><div class="statement-total-summary"><span class="statement-issue-date">账单日期：<StatementEditableCell v-if="editable" v-model="statement.issue_date" label="账单日期" type="date" /><template v-else>{{statement.issue_date||'—'}}</template></span><span>{{statement.pending.length?'合计（已登记金额）':'合计'}}</span></div></td><td :colspan="interactive?3:2"><div v-for="(amount,currency) in displayTotals" :key="currency">{{currency}} {{amount}}</div></td></tr></tfoot>
    </table><img v-if="statement.rows.length && statement.stamp_image" class="statement-stamp" :src="statement.stamp_image" alt="对账单印章" /></div>
    <section v-if="statement.private_settings_available !== false" class="statement-account"><h4>收款账户信息</h4><p>开户行：<StatementEditableCell v-if="editable" v-model="statement.settings.bank_name" label="开户行" /><template v-else>{{statement.settings.bank_name}}</template></p><p>账户名：<StatementEditableCell v-if="editable" v-model="statement.settings.account_name" label="账户名" /><template v-else>{{statement.settings.account_name}}</template></p><p>账号：<StatementEditableCell v-if="editable" v-model="statement.settings.account_number" label="账号" /><template v-else>{{statement.settings.account_number}}</template></p></section>
    <p v-if="statement.pending.length" class="statement-incomplete">待补资料：{{statement.pending.join('；')}}</p>
  </article>
</template>
<script setup>
import {computed} from 'vue'
import {statementUnitPrice,statementColumnWeights,statementBasis,statementTitle,statementTaxLabel,isFixedStatementRow} from '@/utils/statementFormatting'
import StatementEditableCell from './StatementEditableCell.vue'
const hasCustomerOrder=computed(()=>props.statement.rows.some(row=>String(row.customer_order_no||'').trim()))
const hasOrigin=computed(()=>props.statement.rows.some(row=>row.origin_client_id||row.origin_client_name))
const showUnitPrice=computed(()=>!props.statement.rows.length||props.statement.rows.some(row=>!isFixedStatementRow(row)))
const mixedTax=computed(()=>statementTaxLabel(props.statement).includes('按项目'))
const visibleColumnWeights=computed(()=>Object.fromEntries(Object.entries(statementColumnWeights)
  .filter(([key])=>key!=='unit_price'||showUnitPrice.value)))
const columnWidth=weight=>`${weight/(Object.values(visibleColumnWeights.value).reduce((a,b)=>a+b,0)+(hasOrigin.value?24:0)+(hasCustomerOrder.value?24:0))*100}%`
const props=defineProps({statement:{type:Object,required:true},interactive:Boolean,editable:Boolean,canWrite:Boolean,canEdit:Boolean,selected:{type:Array,default:()=>[]}})
const displayTotals=computed(()=>{
  if(!props.editable)return props.statement.totals
  const totals={}
  for(const row of props.statement.rows){
    if(row.counted_in_total===false||row.subtotal==null||row.subtotal==='')continue
    const match=String(row.subtotal).match(/^(-?)(\d{1,14})(?:\.(\d{0,2}))?$/)
    if(!match)continue
    const cents=(BigInt(match[2])*100n+BigInt((match[3]||'').padEnd(2,'0')))*(match[1]?-1n:1n)
    totals[row.currency]=(totals[row.currency]||0n)+cents
  }
  return Object.fromEntries(Object.entries(totals).map(([currency,value])=>{const abs=value<0n?-value:value;return [currency,`${value<0n?'-':''}${abs/100n}.${String(abs%100n).padStart(2,'0')}`]}))
})
const emit=defineEmits(['edit','select','task-drag','task-pointer','open-order'])
function startTaskDrag(event,row){if(!props.interactive||!props.canWrite){event.preventDefault();return}event.stopPropagation();event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-statement-tasks',JSON.stringify(row.task_ids));emit('task-drag',row.task_ids)}
</script>
<style scoped>
.statement-paper{padding:20px;background:white;color:#222;font-family:'Microsoft YaHei',sans-serif;min-width:760px}.statement-paper h2,.statement-paper h3{text-align:center;margin:0 0 12px}.statement-meta{display:flex;justify-content:space-between;gap:12px;margin:16px 0;white-space:pre-wrap}.statement-table-wrap{position:relative}.statement-table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:12px}.statement-table th,.statement-table td{border:1px solid #888;padding:8px 6px;text-align:center;white-space:pre-wrap;overflow-wrap:anywhere;max-width:260px}.statement-table tfoot{font-weight:bold}.statement-table .statement-total-label{text-align:right;padding-right:20px}.statement-total-summary{display:flex;justify-content:space-between;align-items:center;gap:12px}.statement-issue-date{font-size:11px;font-weight:400;color:#64748b;text-align:left}.statement-issue-date :deep(.statement-editable-cell){width:auto}.statement-table .statement-date{white-space:nowrap;overflow-wrap:normal}.statement-paper h2{font-size:20px}.statement-paper h3{font-size:22px}.statement-stamp{position:absolute;pointer-events:none;width:120px;height:120px;object-fit:contain;left:45%;bottom:-16px;opacity:.85;mix-blend-mode:multiply}.statement-account{margin-top:30px}.statement-account p{margin:6px 0}.statement-incomplete{font-size:12px;color:#a54a21}.statement-reference{background:#f5f7fa}.statement-ui{min-width:48px}tr[draggable=true]{cursor:grab}.statement-ui{cursor:default}.statement-task-handle{border:0;background:transparent;cursor:grab;touch-action:none;padding:4px;font-size:18px}.statement-task-handle:active{cursor:grabbing}
.statement-meta--editable>span{display:flex;align-items:center;gap:6px;flex:1;min-width:0;flex-wrap:wrap}.statement-meta--editable :deep(.statement-editable-cell){flex:1;min-width:100px}.statement-unit-size{display:flex;align-items:center;gap:3px;white-space:nowrap}.statement-unit-size :deep(.statement-editable-cell){flex:1;min-width:0}.statement-account :deep(.statement-editable-cell){max-width:600px}.statement-meta--editable select{background:white;border:1px solid #cbd5e1;padding:4px}
.statement-order-link{border:0;padding:0;background:transparent;font:inherit;color:var(--el-color-primary);cursor:pointer;text-align:inherit}.statement-order-link:hover{text-decoration:underline}
</style>
