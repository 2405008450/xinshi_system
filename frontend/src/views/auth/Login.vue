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
          <h1 class="system-title">系统</h1>
          <p class="system-subtitle">专业翻译项目管理平台</p>
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
            <el-form-item>
              <el-button
                type="primary"
                @click="handleLogin"
                :loading="loading"
                size="large"
                class="login-button"
              >
                {{ loading ? '登录中...' : '登录' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <div class="login-footer">
          <el-text type="info" size="small">© 2026 系统 版权所有</el-text>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, OfficeBuilding } from '@element-plus/icons-vue'
import api from '@/api/index'
import { getDefaultRoute } from '@/utils/permission'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
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
  try {
    const { login } = await import('@/api/auth')
    const res = await login(loginForm)
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

    await router.replace(getDefaultRoute())
    ElMessage.success('登录成功')
  } catch (error) {
    ElMessage.error(error.detail || error.message || '登录或页面加载失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
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
