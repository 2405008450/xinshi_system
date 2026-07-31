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

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="用户名">
        <el-input
          v-model="searchForm.username"
          placeholder="请输入用户名"
          clearable
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input
          v-model="searchForm.full_name"
          placeholder="请输入姓名"
          clearable
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border>
      <el-table-column prop="username" label="用户名" width="150" />
      <el-table-column prop="full_name" label="全名" width="150" />
      <el-table-column prop="email" label="邮箱" width="200" />
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
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="290" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="canAssignRoles"
            type="success"
            size="small"
            @click="handleAssignRoles(row)"
          >
            分配角色
          </el-button>
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
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
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!form.id" />
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
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
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
      <el-form label-width="90px" class="role-form">
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
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRoles" @click="saveUserRoles">
          保存角色
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Plus } from '@element-plus/icons-vue'
import * as userApi from '@/api/users'
import * as userRoleApi from '@/api/userRoles'
import { getRoles } from '@/api/roles'
import { hasPermission } from '@/utils/permission'

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

const tableData = ref([])
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0
})

const searchForm = reactive({
  username: '',
  full_name: ''
})

const form = reactive({
  id: null,
  username: '',
  password: '',
  full_name: '',
  email: '',
  is_active: true
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const userParams = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    if (searchForm.username) userParams.username = searchForm.username
    if (searchForm.full_name) userParams.full_name = searchForm.full_name

    const requests = [
      userApi.getUsers(userParams),
      userApi.getUserCount({
        username: userParams.username,
        full_name: userParams.full_name
      })
    ]
    if (canAssignRoles.value) {
      requests.push(userRoleApi.getUserRoles({ skip: 0, limit: 5000 }))
    }
    const [res, countRes, roleRows = []] = await Promise.all(requests)
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
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const resetSearch = () => {
  searchForm.username = ''
  searchForm.full_name = ''
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
    is_active: row.is_active
  })
  dialogVisible.value = true
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
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (form.id) {
          const updateData = { ...form }
          delete updateData.password
          delete updateData.id
          await userApi.updateUser(form.id, updateData)
          ElMessage.success('更新成功')
        } else {
          await userApi.createUser(form)
          ElMessage.success('创建成功')
        }
        dialogVisible.value = false
        fetchData()
      } catch (error) {
        ElMessage.error(error.detail || '操作失败')
      }
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
    is_active: true
  })
  formRef.value?.resetFields()
}

onMounted(() => {
  fetchData()
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
</style>
