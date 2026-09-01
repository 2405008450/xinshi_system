<template>
  <div class="profile-page">
    <el-card shadow="never" class="profile-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>个人中心</h2>
            <p>查看个人账号及项目、工作报告所使用的发件邮箱状态。</p>
          </div>
          <el-tag :type="statusType" effect="plain">{{ statusLabel }}</el-tag>
        </div>
      </template>

      <el-alert
        title="企业邮箱和 SMTP 发件凭据由管理员统一维护。如需新增、替换或重新验证，请联系系统管理员。"
        type="info"
        :closable="false"
        show-icon
      />

      <el-form label-position="top" class="profile-form" @submit.prevent>
        <el-row :gutter="18">
          <el-col :xs="24" :sm="12">
            <el-form-item label="登录账号">
              <ReadonlyField
                :model-value="session.username"
                source="auto"
                tooltip="登录账号由管理员维护，可选中复制"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="姓名">
              <ReadonlyField
                :model-value="session.full_name"
                source="auto"
                tooltip="姓名由管理员维护，可选中复制"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="企业邮箱">
              <ReadonlyField
                :model-value="mailAccount.email"
                source="auto"
                :placeholder="mailAccount.email ? '' : '未配置，请联系管理员'"
                tooltip="企业邮箱由管理员维护，可选中复制"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="最近验证时间">
              <ReadonlyField
                :model-value="formatDateTime(mailAccount.verified_at)"
                source="auto"
                placeholder="尚未验证"
                tooltip="由系统记录的最近 SMTP 验证时间"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">SMTP 发件状态</el-divider>
        <el-alert
          :title="mailStatusDescription"
          :type="mailAccount.is_verified ? 'success' : 'warning'"
          :closable="false"
          show-icon
        />
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { getCurrentSession, getPersonalMailAccount } from '@/api/auth'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

const session = reactive({ username: '', full_name: '' })
const mailAccount = reactive({
  email: null,
  is_bound: false,
  is_verified: false,
  verified_at: null,
  updated_at: null,
})

const statusLabel = computed(() => {
  if (mailAccount.is_verified) return '邮箱已验证'
  if (mailAccount.is_bound) return '邮箱待验证'
  return '邮箱未绑定'
})
const statusType = computed(() => mailAccount.is_verified ? 'success' : (mailAccount.is_bound ? 'warning' : 'info'))
const mailStatusDescription = computed(() => {
  if (mailAccount.is_verified) return '发件邮箱已经由管理员配置并验证，可以发送项目邮件和工作报告。'
  if (mailAccount.is_bound) return '管理员已经保存发件凭据，但尚未通过 SMTP 验证，请联系管理员重新验证。'
  if (mailAccount.email) return '企业邮箱已维护，但管理员尚未配置 SMTP 发件凭据。'
  return '尚未维护企业邮箱，请联系管理员配置。'
})
async function load() {
  try {
    const [sessionData, accountData] = await Promise.all([
      getCurrentSession(),
      getPersonalMailAccount(),
    ])
    Object.assign(session, sessionData)
    Object.assign(mailAccount, accountData)
  } catch (error) {
    ElMessage.error(error?.detail || '加载个人邮箱配置失败')
  }
}

onMounted(load)
</script>

<style scoped>
.profile-page { display: flex; justify-content: center; padding: 8px 0 24px; }
.profile-card { width: min(860px, 100%); }
.card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.card-header h2 { margin: 0; color: var(--el-text-color-primary); font-size: 20px; }
.card-header p { margin: 6px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.profile-form { margin-top: 20px; }
@media (max-width: 600px) {
  .card-header { align-items: stretch; flex-direction: column; }
}
</style>
