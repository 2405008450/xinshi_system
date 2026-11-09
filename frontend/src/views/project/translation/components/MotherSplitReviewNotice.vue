<template>
  <el-alert v-if="review?.required" type="error" :closable="false" show-icon title="母订单信息需要调整">
    <p>原项目“{{ review.originalName }}”已保留为第一个子订单。母订单名称已去掉扩展名，请修改为汇总项目名称，并核对服务内容、翻译方向、字数统计、时间、要求、进度、路径及价格等原项目内容。</p>
    <el-button type="danger" plain @click="$emit('edit')">编辑母订单</el-button>
  </el-alert>
</template>
<script setup>defineProps({review:Object});defineEmits(['edit'])</script>
