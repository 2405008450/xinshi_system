<template><ProjectOperationHelp title="口译操作帮助" module-label="口译" intro="了解如何填写口译项目，以及项目名称和需求发布的生成规则。" :sections="interpretationHelpSections" :updated-at="interpretationHelpUpdatedAt" id-prefix="interpretation-help-" search-placeholder="搜索帮助，例如：项目名称、需求发布、语言 人数、客户选定" /></template>
<script setup>
import ProjectOperationHelp from '@/components/common/ProjectOperationHelp.vue'
import {interpretationHelpSections,interpretationHelpUpdatedAt} from './interpretationHelpContent'
</script>
