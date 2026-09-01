<template>
  <div class="login-container">
    <div class="login-background">
      <div class="background-shapes">
        <div class="shape shape-1"></div>
        <div class="shape shape-2"></div>
        <div class="shape shape-3"></div>
      </div>
    </div>
    <div class="login-content">
      <div class="login-card-wrapper">
        <div class="login-logo">
          <div class="logo-icon">
            <el-icon :size="48"><OfficeBuilding /></el-icon>
          </div>
          <h1 class="system-title">项目管理</h1>
          <p class="system-subtitle">综合业务项目管理平台</p>
        </div>
        <el-card class="login-card" shadow="always">
          <template #header>
            <div class="card-header">
              <h2>欢迎登录</h2>
            </div>
          </template>
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="rules"
            label-width="0"
            class="login-form"
          >
            <el-form-item prop="username">
              <el-input
                v-model="loginForm.username"
                placeholder="请输入用户名"
                size="large"
                :prefix-icon="User"
                clearable
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                size="large"
                :prefix-icon="Lock"
                show-password
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            <el-form-item v-if="captchaRequired" prop="captchaCode">
              <div class="captcha-row">
                <el-input
                  ref="captchaInputRef"
                  v-model="loginForm.captchaCode"
                  placeholder="请输入验证码"
                  size="large"
                  :prefix-icon="Picture"
                  maxlength="6"
                  autocapitalize="characters"
                  :spellcheck="false"
                  clearable
                  @input="normalizeCaptchaInput"
                  @keyup.enter="handleLogin"
                />
                <button
                  type="button"
                  class="captcha-image"
                  :disabled="captchaLoading"
                  title="点击更换验证码"
                  @click="refreshCaptcha"
                >
                  <img v-if="captchaImage" :src="captchaImage" alt="点击更换验证码" />
                  <span v-else class="captcha-placeholder">加载中</span>
                </button>
              </div>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                @click="handleLogin"
                :loading="loading"
                size="large"
                class="login-button"
              >
                {{ loading ? loginStatusText : '登录' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <div class="login-footer">
          <el-text type="info" size="small">© 2026 综合业务项目管理平台 版权所有</el-text>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, OfficeBuilding, Picture } from '@element-plus/icons-vue'
import { checkCaptchaRequired, fetchCaptcha, login } from '@/api/auth'
import { getDefaultRoute } from '@/utils/permission'

const router = useRouter()
const loginFormRef = ref(null)
const captchaInputRef = ref(null)
const loading = ref(false)
const loginStatusText = ref('正在验证账号...')
const captchaRequired = ref(false)
const captchaLoading = ref(false)
const captchaId = ref('')
const captchaImage = ref('')
let preloadHandle = null

const preloadLandingViews = () => {
  preloadHandle = null
  Promise.allSettled([
    import('@/views/schedule/WorkDashboard.vue'),
    import('@/views/dashboard/Dashboard.vue')
  ])
}

const refreshCaptcha = async () => {
  if (captchaLoading.value) return
  captchaLoading.value = true
  captchaId.value = ''
  captchaImage.value = ''
  try {
    const res = await fetchCaptcha()
    captchaId.value = res.captcha_id
    captchaImage.value = res.image
  } catch (error) {
    ElMessage.error(error.detail || '验证码获取失败，请稍后重试')
  } finally {
    captchaLoading.value = false
  }
}

const enableCaptcha = async ({ focus = false } = {}) => {
  captchaRequired.value = true
  loginForm.captchaCode = ''
  await refreshCaptcha()
  if (!focus) return
  await nextTick()
  captchaInputRef.value?.focus?.()
}

onMounted(() => {
  if ('requestIdleCallback' in window) {
    preloadHandle = window.requestIdleCallback(preloadLandingViews, { timeout: 1000 })
  } else {
    preloadHandle = window.setTimeout(preloadLandingViews, 150)
  }
  // 探测失败不阻塞登录：真正需要验证码时后端会在登录响应头中告知。
  checkCaptchaRequired()
    .then((res) => (res?.required ? enableCaptcha() : null))
    .catch(() => {})
})

onBeforeUnmount(() => {
  if (preloadHandle === null) return
  if ('cancelIdleCallback' in window) {
    window.cancelIdleCallback(preloadHandle)
  } else {
    window.clearTimeout(preloadHandle)
  }
})

const loginForm = reactive({
  username: '',
  password: '',
  captchaCode: ''
})

const normalizeCaptchaCode = (value) => String(value || '').normalize('NFKC').trim().toUpperCase()

const normalizeCaptchaInput = (value) => {
  loginForm.captchaCode = String(value || '').normalize('NFKC').toUpperCase()
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ],
  captchaCode: [
    {
      validator: (_rule, value, callback) => {
        if (captchaRequired.value && !String(value || '').trim()) {
          callback(new Error('请输入验证码'))
          return
        }
        callback()
      },
      trigger: 'blur'
    }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  try {
    await loginFormRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  loginStatusText.value = '正在验证账号...'
  const submittedWithCaptcha = captchaRequired.value
  try {
    const payload = { username: loginForm.username, password: loginForm.password }
    if (submittedWithCaptcha) {
      payload.captcha_id = captchaId.value
      payload.captcha_code = normalizeCaptchaCode(loginForm.captchaCode)
    }
    const res = await login(payload)
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user_id', res.user_id)
    const raw = Array.isArray(res.roles) ? res.roles : []
    const roles = raw.map((r) => (typeof r === 'string' ? r : (r && (r.role_name ?? r.name ?? r)) || '')).filter(Boolean)
    localStorage.setItem('user_roles', JSON.stringify(roles))
    localStorage.setItem(
      'user_permissions',
      JSON.stringify(Array.isArray(res.permissions) ? res.permissions : [])
    )
    localStorage.setItem('user_name', loginForm.username || '')
    localStorage.setItem('user_full_name', res.full_name || res.username || loginForm.username || '')

    loginStatusText.value = '正在进入系统...'
    await router.replace(getDefaultRoute())
    ElMessage.success('登录成功')
  } catch (error) {
    // 验证码是一次性的，只要本次提交带过或后端要求补验证码，都换一张新图。
    const serverRequiresCaptcha = error.response?.headers?.['x-login-captcha-required'] === '1'
    if (serverRequiresCaptcha || submittedWithCaptcha) {
      await enableCaptcha({ focus: !submittedWithCaptcha })
    }
    ElMessage.error(error.detail || error.message || '登录或页面加载失败')
  } finally {
    loading.value = false
    loginStatusText.value = '正在验证账号...'
  }
}
</script>

<style scoped>
.login-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 100%;
  overflow: hidden;
  background: linear-gradient(135deg, var(--color-sidebar-deep) 0%, var(--color-primary) 100%);
}

.login-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  z-index: 0;
}

.background-shapes {
  position: relative;
  width: 100%;
  height: 100%;
}

.shape {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
}

.shape-1 {
  width: 300px;
  height: 300px;
  top: -100px;
  left: -100px;
}

.shape-2 {
  width: 200px;
  height: 200px;
  bottom: -50px;
  right: -50px;
}

.shape-3 {
  width: 150px;
  height: 150px;
  top: 50%;
  right: 10%;
}

.login-content {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1200px;
  padding: 40px 20px;
}

.login-card-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 30px;
}

.login-logo {
  text-align: center;
  color: #fff;
}

.logo-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: var(--radius-xl);
  margin-bottom: 20px;
  border: 1px solid rgba(255, 255, 255, 0.14);
}

.system-title {
  font-size: 36px;
  font-weight: 700;
  margin: 0 0 10px 0;
  letter-spacing: 2px;
}

.system-subtitle {
  font-size: 16px;
  margin: 0;
  opacity: 0.9;
  font-weight: 300;
}

.login-card {
  width: 100%;
  max-width: 420px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-dropdown);
}

.login-card :deep(.el-card__header) {
  background: var(--color-primary);
  border-bottom: 1px solid var(--color-primary-hover);
  padding: 30px;
}

.card-header {
  text-align: center;
}

.card-header h2 {
  margin: 0;
  color: #fff;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: 1px;
}

.login-form {
  padding: 30px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 24px;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: var(--radius-md);
  transition: box-shadow 180ms ease;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--color-primary) inset;
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.captcha-row :deep(.el-input) {
  flex: 1;
  min-width: 0;
}

.captcha-image {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 120px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--el-border-color);
  border-radius: var(--radius-md);
  background: #f1f5f9;
  cursor: pointer;
  overflow: hidden;
  transition: border-color 180ms ease;
}

.captcha-image:hover:not(:disabled) {
  border-color: var(--color-primary);
}

.captcha-image:disabled {
  cursor: progress;
}

.captcha-image img {
  display: block;
  width: 100%;
  height: 100%;
}

.captcha-placeholder {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.login-button {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  border: none;
  transition: background-color 180ms ease;
}

.login-button:hover {
  background: var(--color-primary-hover);
}

.login-button:active {
  background: var(--color-primary-active);
}

.login-footer {
  text-align: center;
}

.login-footer :deep(.el-text) {
  color: rgba(255, 255, 255, 0.8);
}

@media (max-width: 768px) {
  .login-card {
    max-width: 100%;
  }
  
  .system-title {
    font-size: 28px;
  }

  .login-content {
    padding: 24px 16px;
  }

  .login-form {
    padding: 24px 20px;
  }
}
</style>
