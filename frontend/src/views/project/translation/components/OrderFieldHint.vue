<template>
  <div v-if="inherited || difference" class="order-field-hint">
    <span v-if="inherited" class="inheritance-label">来自上级（可编辑）</span>
    <template v-if="difference">
      <details v-if="field === 'languagePair' && languageValues.length > 120" class="field-difference"><summary>下级有不同翻译方向，点击展开</summary><div class="difference-item">{{ languageValues }}</div></details>
      <div v-else-if="field === 'languagePair'" class="field-difference">下级有不同翻译方向：{{ languageValues }}</div>
      <details v-else-if="shouldFold" class="field-difference">
        <summary>{{ difference.count }} 个下级订单有不同内容，点击展开</summary>
        <div v-for="item in difference.items" :key="item.orderNo" class="difference-item"><strong>{{ item.orderNo }}{{ item.includesDescendants ? '（含全部下级）' : '' }}</strong><div>{{ display(item.value) }}</div></div>
      </details>
      <div v-else class="field-difference">
        <div>{{ difference.count }} 个下级订单有不同内容：</div>
        <div v-for="item in difference.items" :key="item.orderNo" class="difference-item"><strong>{{ item.orderNo }}{{ item.includesDescendants ? '（含全部下级）' : '' }}</strong><div>{{ display(item.value) }}</div></div>
      </div>
    </template>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import {formatBusinessDateTimeMinute} from '@/utils/dateTime'
import {getProjectStatusOptions} from '@/utils/projectStatus'
const props=defineProps({order:{type:Object,required:true},field:{type:String,required:true}})
const snake=computed(()=>props.field.replace(/[A-Z]/g,c=>'_'+c.toLowerCase()))
const inherited=computed(()=>props.order.inheritedFields?.includes(snake.value))
const difference=computed(()=>props.order.childFieldDifferences?.[props.field])
const shouldFold=computed(()=>difference.value?.items.length>3||difference.value?.items.some(item=>String(item.value||'').length>160))
const display=value=>props.field==='customerDeadlineTime'?formatBusinessDateTimeMinute(value):props.field==='status'?(getProjectStatusOptions('translation').find(item=>item.value===value)?.label||value||'（空）'):value||'（空）'
const languageValues=computed(()=>[...new Set(difference.value?.items.map(item=>display(item.value))||[])].join('；'))
</script>
<style scoped>
.order-field-hint{flex-basis:100%;width:100%;font-size:12px;line-height:1.6;overflow-wrap:anywhere}.inheritance-label{color:#64748b}.field-difference{margin-top:5px;padding:6px 10px;border-left:3px solid #d97706;background:#fffbeb;color:#92400e}.field-difference summary{cursor:pointer}.difference-item{margin-top:4px;white-space:pre-wrap;max-height:160px;overflow:auto;user-select:text}
</style>
