<template><span v-if="!items.length">无</span><span v-else class="project-statement-links"><RouterLink v-for="item in items" :key="`${item.boardId}:${item.month}`" :to="{name:'CustomerStatementPage',params:{clientId:item.clientId,boardId:item.boardId},query:{month:item.month}}" :title="`${item.boardName} · ${item.month}（打开对账单页面）`" @click.stop>{{item.month}}</RouterLink></span></template>
<script setup>
import {computed} from 'vue'
import {RouterLink} from 'vue-router'
const props=defineProps({value:{type:Array,default:()=>[]}})
const items=computed(()=>props.value.flatMap(board=>(board.months||[]).map(month=>({...board,month}))))
</script>
<style scoped>.project-statement-links{display:flex;flex-wrap:wrap;gap:4px 10px}.project-statement-links a{color:var(--el-color-primary);text-decoration:none}.project-statement-links a:hover{text-decoration:underline}</style>
