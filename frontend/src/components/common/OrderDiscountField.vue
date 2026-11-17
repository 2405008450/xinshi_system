<template>
  <el-input-number v-model="discount" :min="1" :max="99" :precision="0" :controls="false"
    :disabled="disabled" :aria-label="label" placeholder="01–99" @change="emit('commit')">
    <template #suffix>折</template>
  </el-input-number>
</template>

<script setup>
defineProps({disabled:Boolean,label:{type:String,default:'折扣'}})
const discount=defineModel({type:Number})
const emit=defineEmits(['commit'])
</script>
