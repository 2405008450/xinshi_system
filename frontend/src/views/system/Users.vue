<template>
  <el-card class="page-card">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><User /></el-icon>
          <span class="header-title">用户管理</span>
        </div>
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增用户</el-button>
      </div>
    </template>

    <el-alert
      class="mail-account-guide"
      title="发件邮箱由管理员统一维护：先填写用户的企业邮箱地址，再点击列表中的“配置凭据”填写 SMTP 密码或授权码并验证。"
      type="info"
      :closable="false"
      show-icon
    />

    <AppForm :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="用户名">
        <el-input
          v-model="searchForm.username"
          placeholder="请输入用户名"
          clearable
          @input="handleTextInput"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input
          v-model="searchForm.full_name"
          placeholder="请输入姓名"
          clearable
          @input="handleTextInput"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="部门">
        <el-select v-model="searchForm.department" clearable placeholder="全部部门" style="width: 150px" @change="handleSearch">
          <el-option v-for="department in departments" :key="department" :label="department" :value="department" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </AppForm>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="username" label="用户名" width="150" />
      <el-table-column prop="full_name" label="全名" width="150" />
      <el-table-column prop="department" label="部门" width="120">
        <template #default="{ row }">{{ normalizeDepartment(row.department) || '未分部门' }}</template>
      </el-table-column>
      <el-table-column prop="email" label="邮箱" width="200" />
      <el-table-column label="邮件资料" min-width="240">
        <template #default="{ row }">
          <div class="mail-profile-cell">
            <span class="mail-profile-name" :title="row.mail_display_name || ''">
              {{ row.mail_display_name || row.full_name || row.username }}
            </span>
            <el-tag size="small" :type="row.mail_signature_enabled ? 'success' : 'info'">
              {{ row.mail_signature_enabled ? '签名已启用' : '无签名' }}
            </el-tag>
            <el-button v-if="canManageMailProfile" type="primary" link size="small" @click="openMailProfileDialog(row)">管理</el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="发件邮箱" width="170" align="center">
        <template #default="{ row }">
          <div class="mail-account-cell">
            <el-tag
              size="small"
              :type="row.mail_account_verified ? 'success' : (row.mail_account_bound ? 'warning' : 'info')"
            >
              {{ row.mail_account_verified ? '已验证' : (row.mail_account_bound ? '待验证' : '未配置') }}
            </el-tag>
            <el-button
              v-if="canManageMailAccount"
              type="primary"
              link
              size="small"
              @click="openMailAccountDialog(row)"
            >配置凭据</el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="角色" min-width="220">
        <template #default="{ row }">
          <template v-if="row.roles?.length">
            <el-tag
              v-for="role in row.roles"
              :key="role.id"
              class="role-tag"
              type="info"
            >
              {{ role.role_name }}
            </el-tag>
          </template>
          <el-text v-else type="info">未分配角色</el-text>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton
            v-if="canAssignRoles"
            action="assign"
            label="分配角色"
            @click="handleAssignRoles(row)"
          />
          <TableActionButton
            v-if="canResetPassword"
            action="password"
            @click="handleResetPassword(row)"
          />
          <TableActionButton action="edit" @click="handleEdit(row)" />
          <el-button v-if="canManageSchedule" type="primary" link size="small" @click="handleShiftSettings(row)">排班设置</el-button>
          <TableActionButton action="delete" @click="handleDelete(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      style="margin-top: 20px"
    />

    <!-- 对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      @close="resetForm"
    >
      <AppForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="!form.id">
          <el-input v-model="form.password" type="password" />
        </el-form-item>
        <el-form-item label="全名" prop="full_name">
          <el-input v-model="form.full_name" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-select v-model="form.department" clearable placeholder="请选择部门" style="width: 100%">
            <el-option v-for="department in departments" :key="department" :label="department" :value="department" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="mailProfileDialogVisible"
      title="用户邮件资料"
      width="min(860px, calc(100vw - 32px))"
      top="5vh"
      class="user-mail-profile-dialog"
      :close-on-click-modal="false"
      @closed="resetMailProfileDialog"
    >
      <div v-loading="mailProfileLoading" class="mail-profile-dialog-body">
        <el-alert
          :title="`当前用户：${mailProfileTargetUser?.full_name || mailProfileTargetUser?.username || ''}`"
          description="邮件显示名用于收件人和抄送栏；启用签名后，系统会在邮件发送时自动追加并保存快照。"
          type="info"
          :closable="false"
          show-icon
        />
        <AppForm :model="mailProfileForm" label-position="top" @submit.prevent>
          <el-form-item label="邮件显示名">
            <el-input
              v-model="mailProfileForm.recipient_display_name"
              maxlength="255"
              show-word-limit
              :placeholder="mailProfileTargetUser?.full_name || mailProfileTargetUser?.username || '请输入邮件显示名'"
            />
          </el-form-item>
          <el-form-item label="启用邮件签名">
            <el-switch v-model="mailProfileForm.signature_enabled" />
          </el-form-item>
          <el-form-item label="富文本签名">
            <MailSignatureEditor
              v-model="mailProfileForm.signature_html"
              v-model:text-value="mailProfileForm.signature_text"
            />
          </el-form-item>
        </AppForm>
      </div>
      <template #footer>
        <el-button :disabled="mailProfileSaving" @click="mailProfileDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="mailProfileSaving" @click="saveMailProfile">保存邮件资料</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="mailAccountDialogVisible"
      title="配置用户发件邮箱"
      width="min(560px, calc(100vw - 32px))"
      @closed="resetMailAccountDialog"
    >
      <el-alert
        :title="`当前用户：${mailTargetUser?.full_name || mailTargetUser?.username || ''}`"
        description="SMTP 密码或授权码将使用 AES-256-GCM 加密保存，保存后不会在页面或接口中回显。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-descriptions class="mail-account-summary" :column="1" border size="small">
        <el-descriptions-item label="企业邮箱">{{ mailTargetUser?.email || '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="验证状态">
          <el-tag :type="mailAccount.is_verified ? 'success' : (mailAccount.is_bound ? 'warning' : 'info')">
            {{ mailAccount.is_verified ? '已验证' : (mailAccount.is_bound ? '待验证' : '未配置') }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最近验证">{{ formatDateTime(mailAccount.verified_at) || '-' }}</el-descriptions-item>
      </el-descriptions>
      <AppForm label-position="top" class="mail-account-form" @submit.prevent>
        <el-form-item :label="mailAccount.is_bound ? '新 SMTP 密码/授权码（填写后覆盖原凭据）' : 'SMTP 密码/授权码'" required>
          <el-input
            v-model="mailAuthorizationCode"
            type="password"
            show-password
            maxlength="500"
            autocomplete="new-password"
            :disabled="!mailTargetUser?.email"
            placeholder="请输入该企业邮箱的 SMTP 密码或授权码"
            @keyup.enter="saveAndVerifyMailAccount"
          />
        </el-form-item>
      </AppForm>
      <el-alert
        v-if="!mailTargetUser?.email"
        title="请先编辑该用户并填写企业邮箱地址，再配置发件凭据。"
        type="warning"
        :closable="false"
        show-icon
      />
      <template #footer>
        <div class="mail-account-footer">
          <el-button
            v-if="mailAccount.is_bound"
            type="danger"
            plain
            :loading="mailAccountSubmitting"
            @click="removeMailAccount"
          >解除绑定</el-button>
          <span class="footer-spacer" />
          <el-button
            v-if="mailAccount.is_bound"
            :loading="mailAccountSubmitting"
            @click="verifyMailAccount"
          >重新验证</el-button>
          <el-button
            type="primary"
            :loading="mailAccountSubmitting"
            :disabled="!mailTargetUser?.email || !mailAuthorizationCode.trim()"
            @click="saveAndVerifyMailAccount"
          >保存并验证</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="passwordDialogVisible"
      title="修改用户密码"
      width="480px"
      @closed="resetPasswordForm"
    >
      <el-alert
        :title="`当前用户：${passwordTargetUser?.full_name || passwordTargetUser?.username || ''}`"
        description="系统不会读取或展示该用户的旧密码。修改后请将新密码安全告知用户。"
        type="warning"
        :closable="false"
        show-icon
      />
      <AppForm
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
        class="password-form"
      >
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="passwordForm.newPassword"
            type="password"
            show-password
            autocomplete="new-password"
            maxlength="128"
            placeholder="至少输入 8 个字符"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
            autocomplete="new-password"
            maxlength="128"
            @keyup.enter="submitPasswordReset"
          />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="passwordSubmitting"
          @click="submitPasswordReset"
        >
          确认修改
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="roleDialogVisible"
      title="分配用户角色"
      width="520px"
      @closed="resetRoleForm"
    >
      <el-alert
        :title="`当前用户：${selectedUser?.full_name || selectedUser?.username || ''}`"
        type="info"
        :closable="false"
        show-icon
      />
      <AppForm label-width="90px" class="role-form">
        <el-form-item label="角色">
          <el-select
            v-model="selectedRoleIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择角色"
            style="width: 100%"
          >
            <el-option
              v-for="role in availableRoles"
              :key="role.id"
              :label="role.role_name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRoles" @click="saveUserRoles">
          保存角色
        </el-button>
      </template>
    </el-dialog>
    <EmployeeShiftTemplateDialog v-model="shiftDialogVisible" :employee="shiftEmployee" @saved="fetchData" />
  </el-card>
</template>

<script setup>
import { computed, ref, reactive, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Plus } from '@element-plus/icons-vue'
import * as userApi from '@/api/users'
import * as userRoleApi from '@/api/userRoles'
import { getRoles } from '@/api/roles'
import { hasPermission, isSuperAdmin } from '@/utils/permission'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { DEPARTMENT_NAMES, normalizeDepartment } from '@/constants/departments'
import EmployeeShiftTemplateDialog from '@/views/schedule/components/EmployeeShiftTemplateDialog.vue'
import MailSignatureEditor from '@/components/common/MailSignatureEditor.vue'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const formRef = ref(null)
const roleDialogVisible = ref(false)
const savingRoles = ref(false)
const selectedUser = ref(null)
const selectedRoleIds = ref([])
const availableRoles = ref([])
const userRoleRows = ref([])
const canAssignRoles = computed(() => hasPermission('system:user_roles:write'))
const canResetPassword = computed(() => isSuperAdmin())
const canManageSchedule = computed(() => hasPermission('schedule:write'))
const canManageMailAccount = computed(() => hasPermission('system:users:write'))
const canManageMailProfile = computed(() => hasPermission('system:users:write'))
const departments = DEPARTMENT_NAMES
const shiftDialogVisible = ref(false)
const shiftEmployee = ref(null)
const passwordDialogVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordFormRef = ref(null)
const passwordTargetUser = ref(null)
const passwordForm = reactive({
  newPassword: '',
  confirmPassword: ''
})
const mailAccountDialogVisible = ref(false)
const mailAccountSubmitting = ref(false)
const mailTargetUser = ref(null)
const mailAuthorizationCode = ref('')
const mailAccount = reactive({
  email: null,
  is_bound: false,
  is_verified: false,
  verified_at: null,
  updated_at: null
})
const mailProfileDialogVisible = ref(false)
const mailProfileLoading = ref(false)
const mailProfileSaving = ref(false)
const mailProfileTargetUser = ref(null)
const mailProfileForm = reactive({
  recipient_display_name: '',
  signature_html: '',
  signature_text: '',
  signature_enabled: false
})
const validateConfirmPassword = (_rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入新密码'))
    return
  }
  if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const passwordRules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 128, message: '密码长度应为 8 到 128 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const searchForm = reactive({
  username: '',
  full_name: '',
  department: ''
})

const form = reactive({
  id: null,
  username: '',
  password: '',
  full_name: '',
  email: '',
  department: '',
  is_active: true
})

const validateEmail = async (_rule, value) => {
  const email = String(value || '').trim()
  if (!email) return
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new Error('请输入正确的邮箱地址')
  }
  try {
    const result = await userApi.checkEmailAvailability(email, form.id)
    if (!result.available) {
      throw new Error('该邮箱已被其他用户绑定，请使用其他邮箱')
    }
  } catch (error) {
    if (error instanceof Error) throw error
    throw new Error(error.detail || '邮箱校验失败，请稍后重试')
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  email: [{ validator: validateEmail, trigger: 'blur' }]
}

let searchTimer = null
let requestController = null
let requestSequence = 0

const fetchData = async () => {
  requestController?.abort()
  requestController = new AbortController()
  const sequence = ++requestSequence
  loading.value = true
  try {
    const userParams = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    if (searchForm.username) userParams.username = searchForm.username
    if (searchForm.full_name) userParams.full_name = searchForm.full_name
    if (searchForm.department) userParams.department = searchForm.department

    const requests = [
      userApi.getUsers(userParams, requestController.signal),
      userApi.getUserCount({
        username: userParams.username,
        full_name: userParams.full_name,
        department: userParams.department
      }, requestController.signal)
    ]
    if (canAssignRoles.value) {
      requests.push(userRoleApi.getUserRoles({ skip: 0, limit: 5000 }))
    }
    const [res, countRes, roleRows = []] = await Promise.all(requests)
    if (sequence !== requestSequence) return
    userRoleRows.value = roleRows
    tableData.value = res.map((user) => ({
      ...user,
      roles: roleRows
        .filter((item) => item.user_id === user.id)
        .map((item) => ({
          id: item.role_id,
          role_name: item.role_name,
          user_role_id: item.id
        }))
    }))
    pagination.total = countRes?.total || 0

    const lastPage = Math.max(1, Math.ceil(pagination.total / pagination.limit))
    if (pagination.page > lastPage) {
      pagination.page = lastPage
      await fetchData()
    }
  } catch (error) {
    if (error.code !== 'ERR_CANCELED' && sequence === requestSequence) ElMessage.error('获取数据失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

const handleSearch = () => {
  clearTimeout(searchTimer)
  pagination.page = 1
  fetchData()
}

const handleTextInput = (value) => {
  clearTimeout(searchTimer)
  if (!value) return handleSearch()
  searchTimer = setTimeout(handleSearch, 400)
}

const resetSearch = () => {
  searchForm.username = ''
  searchForm.full_name = ''
  searchForm.department = ''
  handleSearch()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchData()
}

const handleCurrentChange = () => {
  fetchData()
}

const handleAssignRoles = async (user) => {
  selectedUser.value = user
  selectedRoleIds.value = (user.roles || []).map((role) => role.id)
  roleDialogVisible.value = true
  if (!availableRoles.value.length) {
    try {
      availableRoles.value = await getRoles({ skip: 0, limit: 1000 })
    } catch (error) {
      ElMessage.error(error.detail || '获取角色列表失败')
    }
  }
}

const saveUserRoles = async () => {
  if (!selectedUser.value) return
  savingRoles.value = true
  try {
    const currentRows = userRoleRows.value.filter(
      (item) => item.user_id === selectedUser.value.id
    )
    const currentIds = new Set(currentRows.map((item) => item.role_id))
    const targetIds = new Set(selectedRoleIds.value)
    const additions = [...targetIds].filter((roleId) => !currentIds.has(roleId))
    const removals = currentRows.filter((item) => !targetIds.has(item.role_id))

    await Promise.all([
      ...additions.map((roleId) =>
        userRoleApi.createUserRole({
          user_id: selectedUser.value.id,
          role_id: roleId
        })
      ),
      ...removals.map((item) => userRoleApi.deleteUserRole(item.id))
    ])
    ElMessage.success('用户角色已更新；该用户重新登录后前端菜单将同步刷新')
    roleDialogVisible.value = false
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '保存角色失败')
  } finally {
    savingRoles.value = false
  }
}

const resetRoleForm = () => {
  selectedUser.value = null
  selectedRoleIds.value = []
}

const handleAdd = () => {
  dialogTitle.value = '新增用户'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑用户'
  Object.assign(form, {
    id: row.id,
    username: row.username,
    password: '',
    full_name: row.full_name || '',
    email: row.email || '',
    department: normalizeDepartment(row.department),
    is_active: row.is_active
  })
  dialogVisible.value = true
}

const handleResetPassword = (row) => {
  passwordTargetUser.value = row
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
  passwordDialogVisible.value = true
}

const handleShiftSettings = (row) => {
  shiftEmployee.value = { ...row, name: row.full_name || row.username }
  shiftDialogVisible.value = true
}

const submitPasswordReset = async () => {
  if (!passwordFormRef.value || !passwordTargetUser.value) return
  try {
    await passwordFormRef.value.validate()
  } catch {
    return
  }

  passwordSubmitting.value = true
  try {
    await userApi.resetUserPassword(
      passwordTargetUser.value.id,
      passwordForm.newPassword
    )
    ElMessage.success('密码修改成功')
    passwordDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.detail || '密码修改失败')
  } finally {
    passwordSubmitting.value = false
  }
}

const resetPasswordForm = () => {
  passwordTargetUser.value = null
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
  passwordFormRef.value?.resetFields()
}

const loadMailAccount = async () => {
  if (!mailTargetUser.value) return
  Object.assign(mailAccount, await userApi.getUserMailAccount(mailTargetUser.value.id))
}

const openMailAccountDialog = async (row) => {
  mailTargetUser.value = row
  mailAuthorizationCode.value = ''
  mailAccountDialogVisible.value = true
  try {
    await loadMailAccount()
  } catch (error) {
    ElMessage.error(error.detail || '加载发件邮箱配置失败')
  }
}

const saveAndVerifyMailAccount = async () => {
  if (!mailTargetUser.value?.email || !mailAuthorizationCode.value.trim()) return
  mailAccountSubmitting.value = true
  try {
    Object.assign(
      mailAccount,
      await userApi.saveUserMailAccount(
        mailTargetUser.value.id,
        mailAuthorizationCode.value.trim()
      )
    )
    mailAuthorizationCode.value = ''
    ElMessage.success('发件邮箱凭据已加密保存并验证')
    await fetchData()
  } catch (error) {
    try { await loadMailAccount() } catch {}
    ElMessage.error(error.detail || '发件邮箱保存或验证失败')
  } finally {
    mailAccountSubmitting.value = false
  }
}

const verifyMailAccount = async () => {
  if (!mailTargetUser.value) return
  mailAccountSubmitting.value = true
  try {
    Object.assign(mailAccount, await userApi.verifyUserMailAccount(mailTargetUser.value.id))
    ElMessage.success('发件邮箱验证成功')
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '发件邮箱验证失败')
  } finally {
    mailAccountSubmitting.value = false
  }
}

const removeMailAccount = async () => {
  if (!mailTargetUser.value) return
  try {
    await ElMessageBox.confirm(
      `确认解除 ${mailTargetUser.value.full_name || mailTargetUser.value.username} 的发件邮箱凭据吗？`,
      '解除发件邮箱绑定',
      { type: 'warning', confirmButtonText: '确认解除', cancelButtonText: '取消' }
    )
    mailAccountSubmitting.value = true
    await userApi.deleteUserMailAccount(mailTargetUser.value.id)
    await loadMailAccount()
    await fetchData()
    ElMessage.success('发件邮箱凭据已解除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.detail || '解除发件邮箱失败')
    }
  } finally {
    mailAccountSubmitting.value = false
  }
}

const resetMailAccountDialog = () => {
  mailTargetUser.value = null
  mailAuthorizationCode.value = ''
  Object.assign(mailAccount, {
    email: null,
    is_bound: false,
    is_verified: false,
    verified_at: null,
    updated_at: null
  })
}

const openMailProfileDialog = async (row) => {
  mailProfileTargetUser.value = row
  mailProfileDialogVisible.value = true
  mailProfileLoading.value = true
  try {
    const profile = await userApi.getUserMailProfile(row.id)
    Object.assign(mailProfileForm, {
      recipient_display_name: profile.recipient_display_name || '',
      signature_html: profile.signature_html || '',
      signature_text: profile.signature_text || '',
      signature_enabled: Boolean(profile.signature_enabled)
    })
  } catch (error) {
    ElMessage.error(error.detail || '加载用户邮件资料失败')
  } finally {
    mailProfileLoading.value = false
  }
}

const saveMailProfile = async () => {
  if (!mailProfileTargetUser.value) return
  if (mailProfileForm.signature_enabled && !mailProfileForm.signature_text.trim()) {
    ElMessage.warning('启用签名前请先填写签名内容')
    return
  }
  mailProfileSaving.value = true
  try {
    await userApi.saveUserMailProfile(mailProfileTargetUser.value.id, {
      recipient_display_name: mailProfileForm.recipient_display_name.trim() || null,
      signature_html: mailProfileForm.signature_html || null,
      signature_enabled: mailProfileForm.signature_enabled
    })
    ElMessage.success('用户邮件资料已保存')
    mailProfileDialogVisible.value = false
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '保存用户邮件资料失败')
  } finally {
    mailProfileSaving.value = false
  }
}

const resetMailProfileDialog = () => {
  mailProfileTargetUser.value = null
  Object.assign(mailProfileForm, {
    recipient_display_name: '',
    signature_html: '',
    signature_text: '',
    signature_enabled: false
  })
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该用户吗？', '提示', {
      type: 'warning'
    })
    await userApi.deleteUser(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid, fields) => {
    if (!valid) {
      const emailError = fields?.email?.[0]?.message
      if (emailError) ElMessage.error(emailError)
      return
    }
    try {
      const payload = {
        ...form,
        email: form.email.trim() || null
      }
      if (form.id) {
        const updateData = { ...payload }
        delete updateData.password
        delete updateData.id
        await userApi.updateUser(form.id, updateData)
        ElMessage.success('更新成功')
      } else {
        await userApi.createUser(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch (error) {
      ElMessage.error(error.detail || '操作失败')
    }
  })
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    username: '',
    password: '',
    full_name: '',
    email: '',
    department: '',
    is_active: true
  })
  formRef.value?.resetFields()
}

onMounted(() => {
  fetchData()
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  requestController?.abort()
})
</script>

<style scoped>
.page-card {
  min-height: calc(100vh - 120px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  font-size: 20px;
  color: var(--color-primary);
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.mail-account-guide {
  margin-bottom: 16px;
}

.mail-account-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.mail-profile-cell{display:flex;align-items:center;gap:6px;min-width:0}.mail-profile-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mail-profile-cell .el-tag,.mail-profile-cell .el-button{flex-shrink:0}.mail-profile-dialog-body{display:flex;flex-direction:column;gap:14px}.mail-profile-dialog-body :deep(.el-form-item__content){display:block}:global(.user-mail-profile-dialog){display:flex;max-height:90vh;overflow:hidden;flex-direction:column}:global(.user-mail-profile-dialog .el-dialog__header),:global(.user-mail-profile-dialog .el-dialog__footer){flex:none}:global(.user-mail-profile-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:global(.user-mail-profile-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}

.mail-account-summary {
  margin-top: 18px;
}

.mail-account-form {
  margin-top: 18px;
}

.mail-account-footer {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 10px;
}

.footer-spacer {
  flex: 1;
}

.el-table {
  margin-top: 16px;
}

.search-form {
  margin-bottom: 4px;
}

.el-table :deep(.el-table__cell) {
  padding: 16px 0;
}

.role-tag {
  margin: 2px 6px 2px 0;
}

.role-form {
  margin-top: 20px;
}

.password-form {
  margin-top: 20px;
}
</style>
