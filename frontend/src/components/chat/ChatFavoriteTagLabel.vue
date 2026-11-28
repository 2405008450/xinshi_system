<template>
 <span class="favorite-tag-label"><i class="favorite-tag-label__color" :style="{background:color}" aria-hidden="true"/><span class="favorite-tag-label__text">{{name}}</span><button v-if="removable" type="button" :disabled="disabled" :aria-label="`移除标签 ${name}`" title="移除这个标签" @click.stop="$emit('remove')">×</button></span>
</template>
<script setup>
defineProps({name:{type:String,default:''},color:{type:String,default:'#2563eb'},removable:Boolean,disabled:Boolean})
defineEmits(['remove'])
</script>
<style scoped>
.favorite-tag-label{display:inline-flex;align-items:center;gap:8px;max-width:100%;vertical-align:middle;line-height:1.6;color:#111827;font-size:13px;font-weight:400}.favorite-tag-label__color{display:inline-block;flex:none;width:14px;height:14px;box-sizing:border-box;border:1px solid #0002;border-radius:1px;box-shadow:inset 0 0 0 1px #ffffff65}.favorite-tag-label__text{min-width:0;overflow-wrap:anywhere;white-space:normal}
.favorite-tag-label>button{border:0;background:transparent;padding:0 2px;color:#64748b;font-size:16px;cursor:pointer}.favorite-tag-label>button:focus-visible{outline:2px solid #5479be}.favorite-tag-label>button:disabled{cursor:wait;opacity:.5}
</style>
