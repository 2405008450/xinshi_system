<template>
  <div class="team-contact-details">
    <el-empty v-if="!contacts.length" description="暂未填写团队对接人" :image-size="48" />
    <section v-for="(contact, index) in contacts" :key="contact.id || index">
      <h4>对接人{{ index + 1 }}</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="姓名">{{ contact.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="昵称">{{ contact.nickname || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系方式" :span="2"><SensitiveContactValue :value="contact.contact_info" :restricted="restricted" /></el-descriptions-item>
      </el-descriptions>
    </section>
  </div>
</template>

<script setup>
import SensitiveContactValue from '@/components/common/SensitiveContactValue.vue'
defineProps({ contacts: { type: Array, default: () => [] }, restricted: { type: Boolean, default: true } })
</script>

<style>
.team-contact-details section + section { margin-top:16px; }
.team-contact-details h4 { margin:0 0 10px; }
.team-contact-details .el-descriptions__table { table-layout:fixed; }
.team-contact-details .el-descriptions__cell { white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
