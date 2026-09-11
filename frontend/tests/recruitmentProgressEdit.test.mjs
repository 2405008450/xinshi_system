import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/views/project/RecruitmentProjects.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/recruitmentProjects.js', import.meta.url), 'utf8')

test('招聘项目人工进度记录支持编辑时间和说明', () => {
  assert.match(page, /v-if="canWrite && !item\.isSystem"[^>]*>编辑<\/el-button>/)
  assert.match(page, /v-model="editingProgressOccurredAt"/)
  assert.match(page, /v-model="editingProgressNote"/)
  assert.match(page, /updateRecruitmentProgress\(activeProject\.value\.id,item\.id/)
  assert.match(page, /progressRows\.value\.sort/)
})

test('招聘项目进度更新接口传递项目和记录标识', () => {
  assert.match(api, /updateRecruitmentProgress = \(projectId, progressId, data\)/)
  assert.match(api, /api\.put\(`\/projects\/recruitment\/\$\{projectId\}\/progress\/\$\{progressId\}`/)
})
