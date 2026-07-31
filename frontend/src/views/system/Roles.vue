<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <span class="title">角色与权限</span>
          <div class="subtitle">角色决定用户可访问的菜单和可执行的后端操作</div>
        </div>
        <el-button v-if="canWrite" type="primary" @click="handleAdd">新增角色</el-button>
      </div>
    </template>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="role_name" label="角色名称" width="180" />
      <el-table-column prop="description" label="描述" min-width="220" />
      <el-table-column label="已授权" min-width="300">
        <template #default="{ row }">
          <el-tag v-if="row.permissions?.includes('*')" type="danger">全部权限</el-tag>
          <template v-else-if="row.permissions?.length">
            <el-tag
              v-for="code in row.permissions.slice(0, 4)"
              :key="code"
              class="permission-tag"
              type="info"
            >
              {{ permissionName(code) }}
            </el-tag>
            <el-tag v-if="row.permissions.length > 4" type="info">
              +{{ row.permissions.length - 4 }}
            </el-tag>
          </template>
          <el-text v-else type="info">尚未授权</el-text>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="canWrite && !isProtectedRole(row)"
            type="success"
            size="small"
            @click="handlePermission(row)"
          >
            配置权限
          </el-button>
          <el-button v-if="canWrite" type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button
            v-if="canWrite && !isProtectedRole(row)"
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="roleDialogVisible" :title="roleDialogTitle" width="520px" @close="resetRoleForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="角色名称" prop="role_name">
          <el-input v-model="form.role_name" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRoleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="permissionDialogVisible" title="配置角色权限" width="760px">
      <el-alert
        :title="`正在配置：${selectedRole?.role_name || ''}`"
        type="info"
        :closable="false"
        show-icon
      />
      <div v-loading="catalogLoading" class="permission-groups">
        <section v-for="group in permissionGroups" :key="group.group" class="permission-group">
          <div class="group-header">
            <strong>{{ group.group }}</strong>
            <el-checkbox
              :model-value="isGroupSelected(group)"
              :indeterminate="isGroupIndeterminate(group)"
              @change="toggleGroup(group, $event)"
            >
              全选
            </el-checkbox>
          </div>
          <el-checkbox-group v-model="selectedPermissions" class="permission-list">
            <el-checkbox
              v-for="permission in group.permissions"
              :key="permission.code"
              :label="permission.code"
            >
              {{ permission.name }}
              <el-text class="permission-code" type="info">{{ permission.code }}</el-text>
            </el-checkbox>
          </el-checkbox-group>
        </section>
      </div>
      <template #footer>
        <el-button @click="permissionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPermissions" @click="savePermissions">
          保存权限
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as roleApi from '@/api/roles'
import { hasPermission } from '@/utils/permission'

const loading = ref(false)
const roleDialogVisible = ref(false)
const permissionDialogVisible = ref(false)
const roleDialogTitle = ref('新增角色')
const formRef = ref(null)
const tableData = ref([])
const permissionGroups = ref([])
const catalogLoading = ref(false)
const savingPermissions = ref(false)
const selectedRole = ref(null)
const selectedPermissions = ref([])

const canWrite = computed(() => hasPermission('system:roles:write'))
const protectedRoles = ['admin', '超级管理员']

const form = reactive({ id: null, role_name: '', description: '' })
const rules = { role_name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }] }

const permissionMap = computed(() => {
  const entries = permissionGroups.value.flatMap((group) =>
    group.permissions.map((permission) => [permission.code, permission.name])
  )
  return Object.fromEntries(entries)
})

const permissionName = (code) => permissionMap.value[code] || code
const isProtectedRole = (role) => protectedRoles.includes(role.role_name)

async function fetchData() {
  loading.value = true
  try {
    tableData.value = await roleApi.getRoles({ skip: 0, limit: 500 })
  } catch (error) {
    ElMessage.error(error.detail || '获取角色失败')
  } finally {
    loading.value = false
  }
}

async function ensureCatalog() {
  if (permissionGroups.value.length) return
  catalogLoading.value = true
  try {
    permissionGroups.value = await roleApi.getPermissionCatalog()
  } finally {
    catalogLoading.value = false
  }
}

function handleAdd() {
  resetRoleForm()
  roleDialogTitle.value = '新增角色'
  roleDialogVisible.value = true
}

function handleEdit(row) {
  Object.assign(form, {
    id: row.id,
    role_name: row.role_name,
    description: row.description || ''
  })
  roleDialogTitle.value = '编辑角色'
  roleDialogVisible.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除角色“${row.role_name}”吗？`, '删除角色', { type: 'warning' })
    await roleApi.deleteRole(row.id)
    ElMessage.success('角色已删除')
    await fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.detail || '删除失败')
  }
}

async function handleRoleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const payload = { role_name: form.role_name, description: form.description }
      if (form.id) await roleApi.updateRole(form.id, payload)
      else await roleApi.createRole(payload)
      ElMessage.success(form.id ? '角色已更新' : '角色已创建')
      roleDialogVisible.value = false
      await fetchData()
    } catch (error) {
      ElMessage.error(error.detail || '保存失败')
    }
  })
}

async function handlePermission(row) {
  selectedRole.value = row
  selectedPermissions.value = [...(row.permissions || [])].filter((code) => code !== '*')
  permissionDialogVisible.value = true
  try {
    await ensureCatalog()
  } catch (error) {
    ElMessage.error(error.detail || '获取权限目录失败')
  }
}

function groupCodes(group) {
  return group.permissions.map((permission) => permission.code)
}

function isGroupSelected(group) {
  const codes = groupCodes(group)
  return codes.length > 0 && codes.every((code) => selectedPermissions.value.includes(code))
}

function isGroupIndeterminate(group) {
  const selectedCount = groupCodes(group).filter((code) => selectedPermissions.value.includes(code)).length
  return selectedCount > 0 && selectedCount < group.permissions.length
}

function toggleGroup(group, checked) {
  const codes = groupCodes(group)
  if (checked) selectedPermissions.value = [...new Set([...selectedPermissions.value, ...codes])]
  else selectedPermissions.value = selectedPermissions.value.filter((code) => !codes.includes(code))
}

async function savePermissions() {
  if (!selectedRole.value) return
  savingPermissions.value = true
  try {
    await roleApi.updateRolePermissions(selectedRole.value.id, selectedPermissions.value)
    ElMessage.success('权限配置已保存，相关用户重新登录后生效')
    permissionDialogVisible.value = false
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '保存权限失败')
  } finally {
    savingPermissions.value = false
  }
}

function resetRoleForm() {
  Object.assign(form, { id: null, role_name: '', description: '' })
  formRef.value?.resetFields()
}

onMounted(async () => {
  await Promise.all([fetchData(), ensureCatalog()])
})
</script>

<style scoped>
.card-header,
.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.subtitle {
  margin-top: 4px;
  color: #909399;
  font-size: 13px;
}
.permission-tag {
  margin: 2px 6px 2px 0;
}
.permission-groups {
  min-height: 240px;
  margin-top: 18px;
}
.permission-group {
  padding: 14px 0;
  border-bottom: 1px solid #ebeef5;
}
.permission-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.permission-list :deep(.el-checkbox) {
  height: auto;
  margin-right: 0;
}
.permission-code {
  display: block;
  margin-left: 24px;
  font-size: 12px;
}
</style>
