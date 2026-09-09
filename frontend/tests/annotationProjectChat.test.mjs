import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const annotationPage = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const chatPanel = readFileSync(new URL('../src/components/ProjectChatPanel.vue', import.meta.url), 'utf8')
const chatApi = readFileSync(new URL('../src/api/projectChat.js', import.meta.url), 'utf8')
const notificationBell = readFileSync(new URL('../src/components/NotificationBell.vue', import.meta.url), 'utf8')

test('标注项目进度弹窗提供纯文本项目沟通页签', () => {
  assert.match(annotationPage, /class="progress-dialog-project__label">订单号<\/span>/)
  assert.match(annotationPage, /class="progress-dialog-project__label">项目名称<\/span>/)
  assert.match(annotationPage, /activeProgressProject\?\.orderNo/)
  assert.match(annotationPage, /<el-tab-pane label="进度记录" name="progress">/)
  assert.match(annotationPage, /<el-tab-pane label="项目沟通" name="chat">/)
  assert.match(annotationPage, /project-type="annotation"/)
  assert.match(annotationPage, /:text-only="true"/)
  assert.match(annotationPage, /:always-enabled="true"/)
  assert.match(annotationPage, /\scompact\s*\/>/)
})

test('纯文本模式不提交富文本或附件字段', () => {
  assert.doesNotMatch(chatPanel, /^\s{6}<template>\s*$/m)
  assert.match(chatPanel, /props\.textOnly\s*\?\s*\{\s*content:/s)
  assert.match(chatPanel, /v-if="textOnly"[\s\S]*type="textarea"/)
  assert.match(chatPanel, /v-if="!textOnly" class="composer-attachments"/)
  assert.match(chatApi, /\/project-chat\/annotation\/\$\{projectId\}/)
})

test('标注聊天提醒可以直达项目沟通页签', () => {
  assert.match(notificationBell, /includes\('project_chat'\).*query\.tab = 'chat'/)
  assert.match(annotationPage, /route\.query\.tab==='chat'/)
  assert.match(annotationPage, /openProgress\(detail,'','chat'\)/)
})

test('项目沟通筛选区使用紧凑的响应式布局', () => {
  assert.match(chatPanel, /'project-chat-panel--compact': compact/)
  assert.match(chatPanel, /compact:\s*\{ type: Boolean, default: false \}/)
  assert.match(chatPanel, /class="chat-filter-bar__range"/)
  assert.match(chatPanel, /class="chat-filter-bar__actions"/)
  assert.match(chatPanel, /\.chat-filter-bar\s*\{[\s\S]*display:\s*flex;[\s\S]*gap:\s*8px 16px;[\s\S]*flex-wrap:\s*wrap;/)
  assert.match(chatPanel, /\.chat-filter-bar__range :deep\(\.el-date-editor\)\s*\{\s*width:\s*360px;/)
  assert.match(chatPanel, /\.project-chat-panel--compact \.chat-filter-bar\s*\{[\s\S]*background:\s*var\(--el-color-primary-light-9\);/)
  assert.match(chatPanel, /\.project-chat-panel--compact \.chat-composer__body\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*flex-end;/)
})
