import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const annotationPage = readFileSync(new URL('../src/views/project/AnnotationProjects.vue', import.meta.url), 'utf8')
const chatPanel = readFileSync(new URL('../src/components/ProjectChatPanel.vue', import.meta.url), 'utf8')
const chatApi = readFileSync(new URL('../src/api/projectChat.js', import.meta.url), 'utf8')
const notificationBell = readFileSync(new URL('../src/components/NotificationBell.vue', import.meta.url), 'utf8')

test('标注项目进度弹窗提供纯文本项目沟通页签', () => {
  assert.match(annotationPage, /<el-tab-pane label="进度记录" name="progress">/)
  assert.match(annotationPage, /<el-tab-pane label="项目沟通" name="chat">/)
  assert.match(annotationPage, /project-type="annotation"/)
  assert.match(annotationPage, /:text-only="true"/)
  assert.match(annotationPage, /:always-enabled="true"/)
})

test('纯文本模式不提交富文本或附件字段', () => {
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
