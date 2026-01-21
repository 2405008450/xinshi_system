<template>
  <div class="mock-switch-container">
    <el-switch
      v-model="mockEnabled"
      @change="handleMockChange"
      active-text="Mock模式"
      inactive-text="真实API"
      inline-prompt
      :active-icon="Platform"
      :inactive-icon="Link"
      size="large"
    />
    <el-tooltip content="刷新页面后生效" placement="bottom">
      <el-icon class="info-icon"><QuestionFilled /></el-icon>
    </el-tooltip>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Platform, Link, QuestionFilled } from '@element-plus/icons-vue'

const mockEnabled = ref(false)

onMounted(() => {
  const mockSetting = localStorage.getItem('USE_MOCK')
  mockEnabled.value = mockSetting === 'true'
})

const handleMockChange = (value) => {
  localStorage.setItem('USE_MOCK', value.toString())
  ElMessage.success({
    message: value ? 'Mock模式已启用，请刷新页面' : 'Mock模式已关闭，请刷新页面',
    duration: 3000
  })
  // 延迟刷新页面
  setTimeout(() => {
    window.location.reload()
  }, 1000)
}
</script>

<style scoped>
.mock-switch-container {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  margin: 12px;
}

.info-icon {
  color: #d1d5db;
  cursor: help;
  font-size: 16px;
}

.info-icon:hover {
  color: #fff;
}
</style>
