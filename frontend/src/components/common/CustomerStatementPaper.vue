<template>
  <article class="statement-paper">
    <h2>{{statement.company}}</h2><h3>{{statement.title}}</h3>
    <div class="statement-meta"><span>客户：{{statement.client_name}}　{{statement.client_code}}</span><span>账单月份：{{statement.month}}　{{statement.tax_included?'含税':'不含税'}}</span></div>
    <div class="statement-table-wrap"><table class="statement-table">
      <thead><tr><th v-if="interactive" class="statement-ui">选择</th><th>订单号</th><th>账单月份</th><th>来稿日期</th><th>项目名称</th><th>翻译方向</th><th>工作量（计价方式）</th><th>单价</th><th>小计</th><th>备注</th><th v-if="interactive" class="statement-ui">操作</th></tr></thead>
      <tbody>
        <tr v-for="row in statement.rows" :key="row._row_id" :draggable="interactive&&canWrite" :class="{'statement-reference':row.counted_in_total===false}" @dragstart="startTaskDrag($event,row)" @dblclick="interactive&&canWrite&&emit('edit',row)">
          <td v-if="interactive" class="statement-ui"><button v-if="canWrite" type="button" class="statement-task-handle" :aria-label="`拖动任务 ${row.order_no}`" title="拖到另一份对账单" @pointerdown.prevent.stop="emit('task-pointer',$event,row.task_ids)">⠿</button><el-checkbox :model-value="row.task_ids.every(id=>selected.includes(id))" :disabled="!canWrite" :aria-label="`选择任务 ${row.order_no}`" @change="emit('select',row.task_ids,$event)" /></td>
          <td>{{row.order_no}}</td><td>{{row.billing_month}}</td><td>{{row.received_date||'-'}}</td><td>{{row.project_name}}</td><td>{{row.language_pair}}</td><td>{{row.quantity??''}}<br />{{row.basis}}</td><td>{{row.unit_price==null?'-':`${row.currency} ${row.unit_price}（${row.unit_label}，每${row.unit_size||1}计价）`}}</td><td>{{row.subtotal==null?'待补':`${row.currency} ${row.subtotal}`}}</td><td>{{row.counted_in_total===false?'汇总参考，不重复计入合计。':''}}{{row.remarks}}</td>
          <td v-if="interactive" class="statement-ui"><el-button v-if="canWrite" link type="primary" @click="emit('edit',row)">修改</el-button></td>
        </tr>
        <tr v-if="!statement.rows.length"><td :colspan="interactive?11:9">暂无任务，可从另一份对账单拖入</td></tr>
      </tbody>
      <tfoot><tr><td :colspan="interactive?8:7">{{statement.pending.length?'合计（已登记金额）':'合计'}}</td><td :colspan="interactive?3:2"><div v-for="(amount,currency) in statement.totals" :key="currency">{{currency}} {{amount}}</div></td></tr></tfoot>
    </table><img v-if="statement.rows.length" class="statement-stamp" :src="statement.stamp_image" alt="对账单印章" /></div>
    <section class="statement-account"><h4>账户信息</h4><p>开户行：{{statement.settings.bank_name}}</p><p>账户名：{{statement.settings.account_name}}</p><p>账号：{{statement.settings.account_number}}</p></section>
    <p v-if="statement.pending.length" class="statement-incomplete">待补资料：{{statement.pending.join('；')}}</p>
  </article>
</template>
<script setup>
const props=defineProps({statement:{type:Object,required:true},interactive:Boolean,canWrite:Boolean,selected:{type:Array,default:()=>[]}})
const emit=defineEmits(['edit','select','task-drag','task-pointer'])
function startTaskDrag(event,row){if(!props.interactive||!props.canWrite){event.preventDefault();return}event.stopPropagation();event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-statement-tasks',JSON.stringify(row.task_ids));emit('task-drag',row.task_ids)}
</script>
<style scoped>
.statement-paper{padding:20px;background:white;color:#222;font-family:'Microsoft YaHei',sans-serif;min-width:760px}.statement-paper h2,.statement-paper h3{text-align:center;margin:0 0 12px}.statement-meta{display:flex;justify-content:space-between;gap:12px;margin:16px 0;white-space:pre-wrap}.statement-table-wrap{position:relative}.statement-table{width:100%;border-collapse:collapse;font-size:12px}.statement-table th,.statement-table td{border:1px solid #888;padding:8px 6px;text-align:center;white-space:pre-wrap;overflow-wrap:anywhere;max-width:260px}.statement-table tfoot{font-weight:bold}.statement-stamp{position:absolute;pointer-events:none;width:120px;height:120px;object-fit:contain;left:45%;bottom:-16px;opacity:.85;mix-blend-mode:multiply}.statement-account{margin-top:30px}.statement-account p{margin:6px 0}.statement-incomplete{font-size:12px;color:#a54a21}.statement-reference{background:#f5f7fa}.statement-ui{min-width:48px}tr[draggable=true]{cursor:grab}.statement-ui{cursor:default}.statement-task-handle{border:0;background:transparent;cursor:grab;touch-action:none;padding:4px;font-size:18px}.statement-task-handle:active{cursor:grabbing}
</style>
