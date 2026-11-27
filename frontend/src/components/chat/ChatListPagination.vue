<template>
  <div class="chat-list-pagination" aria-label="会话分页">
    <el-select :model-value="pageSize" :teleported="teleported" size="small" aria-label="每页条数" @update:model-value="changeSize">
      <el-option v-for="size in [10,20,50]" :key="size" :value="size" :label="`${size} 条/页`" />
    </el-select>
    <el-pagination small :current-page="page" :page-size="pageSize" :total="total" :pager-count="5" layout="prev, pager, next" @current-change="changePage" />
    <small>共 {{ total }} 条</small>
  </div>
</template>
<script setup>
const props = defineProps({ page: {type:Number,default:1}, pageSize: {type:Number,default:20}, total: {type:Number,default:0}, teleported: {type:Boolean,default:true} })
const emit = defineEmits(['update:page','update:pageSize','change'])
function changeSize(size) { if(size===props.pageSize)return;emit('update:pageSize',size);emit('update:page',1);emit('change') }
function changePage(page) { if(page===props.page)return;emit('update:page',page);emit('change') }
</script>
<style scoped>
.chat-list-pagination{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:4px;flex:none;padding:7px 4px;border-top:1px solid #e2e8f0;background:#f9fafc}
.chat-list-pagination>.el-select{width:100px;flex:none}.chat-list-pagination>small{font-size:11px;color:#64748b;white-space:nowrap}
.chat-list-pagination :deep(.el-pagination){margin:0}.chat-list-pagination :deep(.el-pager li){min-width:22px}
</style>
