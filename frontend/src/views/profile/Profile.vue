<template>
  <div class="profile-page">
    <el-card shadow="never" class="common-page-card profile-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>个人中心</h2>
            <p>管理登录密码，查看个人账号和发件邮箱状态。</p>
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

      <AppForm label-position="top" class="profile-form" @submit.prevent>
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
      </AppForm>

      <el-divider content-position="left">修改登录密码</el-divider>
      <p class="password-hint">新密码为 8～128 个字符。修改成功后将退出登录，其他设备也需使用新密码重新登录。</p>
      <AppForm
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        :disabled="passwordSubmitting"
        label-position="top"
        class="password-form"
        @submit.prevent="submitPassword"
      >
        <el-form-item label="当前密码" prop="current_password">
          <el-input v-model="passwordForm.current_password" type="password" show-password
            autocomplete="current-password" placeholder="请输入当前登录密码" :maxlength="1024" />
        </el-form-item>
        <el-row :gutter="18">
          <el-col :xs="24" :sm="12">
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="passwordForm.new_password" type="password" show-password
                autocomplete="new-password" placeholder="请输入至少 8 位的新密码" :maxlength="128" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input v-model="passwordForm.confirm_password" type="password" show-password
                autocomplete="new-password" placeholder="请再次输入新密码" :maxlength="128" />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="password-actions">
          <el-button type="primary" native-type="submit" :loading="passwordSubmitting">修改密码</el-button>
          <el-button :disabled="passwordSubmitting" @click="passwordFormRef?.resetFields()">清空</el-button>
        </div>
      </AppForm>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { getCurrentSession, getPersonalMailAccount, changePersonalPassword } from '@/api/auth'
import { formatBusinessDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { clearAuthSession } from '@/utils/authSession'

const router = useRouter()
const passwordFormRef = ref(null)
const passwordSubmitting = ref(false)
const passwordForm = reactive({ current_password: '', new_password: '', confirm_password: '' })
const passwordRules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 128, message: '新密码长度应为 8 到 128 个字符', trigger: 'blur' },
    { validator: (_rule, value, callback) => callback(value && value === passwordForm.current_password
      ? new Error('新密码不能与当前密码相同') : undefined), trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: (_rule, value, callback) => callback(value !== passwordForm.new_password
      ? new Error('两次输入的新密码不一致') : undefined), trigger: 'blur' },
  ],
}

async function submitPassword() {
  if (passwordSubmitting.value || !passwordFormRef.value) return
  try { await passwordFormRef.value.validate() } catch { return }
  passwordSubmitting.value = true
  try {
    await changePersonalPassword({ ...passwordForm })
  } catch (error) {
    passwordSubmitting.value = false
    await nextTick()
    await passwordFormRef.value?.applyServerErrors(error)
    return
  }
  passwordFormRef.value.resetFields()
  clearAuthSession()
  sessionStorage.setItem('password-change-completed', '1')
  // 整页跳转同时关闭当前页的聊天连接和后台轮询。
  window.location.replace(router.resolve('/login').href)
}

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
    ElMessage.error(error?.detail || '加载个人中心信息失败')
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
.password-hint { margin: 0 0 18px; font-size: 13px; color: var(--el-text-color-secondary); line-height: 1.6; }
.password-actions { display: flex; gap: 12px; }
.password-actions .el-button + .el-button { margin-left: 0; }
@media (max-width: 600px) {
  .card-header { align-items: stretch; flex-direction: column; }
}
</style>
