<template><ProjectDetails ref="details" arrangement /></template>
<script setup>
import {ref} from 'vue'
import ProjectDetails from './ProjectDetails.vue'
const details=ref(null)
const restoreDefaultExclusions=()=>details.value?.restoreDefaultExclusions()
defineExpose({restoreDefaultExclusions})
</script>
