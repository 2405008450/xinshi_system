<template>
  <div v-for="node in nodes" :key="node.id" class="section-nav-node">
    <div class="section-nav-row">
      <button type="button" :class="{'is-active':node.id===activeId}" @click="node.hasContent || allowGroupSelection ? $emit('select',node) : $emit('toggle',node.id)">{{ node.title }}</button>
      <button v-if="node.children?.length" type="button" class="section-nav-toggle" :aria-label="`${expandedIds.has(node.id)?'收起':'展开'}${node.title}`" :aria-expanded="expandedIds.has(node.id)" @click="$emit('toggle',node.id)">{{ expandedIds.has(node.id)?'▾':'▸' }}</button>
    </div>
    <div v-if="node.children?.length" v-show="expandedIds.has(node.id)" class="section-nav-children">
      <DocumentSectionNav :nodes="node.children" :active-id="activeId" :expanded-ids="expandedIds" :allow-group-selection="allowGroupSelection" @select="$emit('select',$event)" @toggle="$emit('toggle',$event)" />
    </div>
  </div>
</template>
<script setup>
defineProps({nodes:{type:Array,default:()=>[]},activeId:String,expandedIds:{type:Set,required:true},allowGroupSelection:Boolean})
defineEmits(['select','toggle'])
</script>
<style scoped>.section-nav-row{display:flex;align-items:center;gap:2px}.section-nav-row button{border:0;background:transparent;color:var(--el-text-color-regular);border-radius:6px;cursor:pointer;text-align:left;padding:10px;min-width:0;overflow-wrap:anywhere;font:inherit;flex:1}.section-nav-row button:hover{background:var(--el-fill-color)}.section-nav-row .is-active{background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-weight:600}.section-nav-row .section-nav-toggle{flex:0 0 30px;text-align:center}.section-nav-children{padding-left:12px}</style>
