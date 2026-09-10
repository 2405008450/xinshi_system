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

test('标注和笔译聊天统一支持多人提醒与私有收藏', () => {
  assert.match(chatPanel, /v-model="composer\.mentionedUserIds"/)
  assert.match(chatPanel, /\smultiple\s/)
  assert.match(chatPanel, /:multiple-limit="20"/)
  assert.match(chatPanel, /collapse-tags-tooltip/)
  assert.match(chatPanel, /messageMentions\(message\)\.slice\(0, 3\)/)
  assert.match(chatPanel, /只看收藏/)
  assert.match(chatPanel, /favorites_only: filters\.favoritesOnly/)
  assert.match(chatPanel, /收藏（仅自己可见）/)
  assert.match(chatApi, /put\(`\/project-chat\/messages\/\$\{messageId\}\/favorite`\)/)
  assert.match(chatApi, /delete\(`\/project-chat\/messages\/\$\{messageId\}\/favorite`\)/)
})

test('标注沟通消息可以带入补充进度且不会影响笔译默认行为', () => {
  assert.match(chatPanel, /canAddToProgress:\s*\{ type: Boolean, default: false \}/)
  assert.match(chatPanel, /defineEmits\(\['add-to-progress'\]\)/)
  assert.match(chatPanel, /v-if="canAddToProgress && String\(message\.content \|\| ''\)\.trim\(\)"/)
  assert.match(chatPanel, /@click="emit\('add-to-progress', message\)"/)
  assert.match(chatPanel, /添加为进度/)
  assert.match(annotationPage, /:can-add-to-progress="canWrite"/)
  assert.match(annotationPage, /@add-to-progress="handleChatMessageToProgress"/)
})

test('沟通消息只预填补充进度并保留两条进度操作路线', () => {
  assert.match(annotationPage, /const handleChatMessageToProgress=async\(message\)=>/)
  assert.match(annotationPage, /statusEntryMode\.value='progress'/)
  assert.match(annotationPage, /projectStatus:activeProgressProject\.value\?\.projectStatus\|\|''/)
  assert.match(annotationPage, /effectiveOn:localDateTimeValue\(effectiveDate\)/)
  assert.match(annotationPage, /changeNote:content/)
  assert.match(annotationPage, /具体进度中已有未保存内容/)
  assert.match(annotationPage, /progressDialogTab\.value='progress'/)
  assert.match(annotationPage, /已从项目沟通带入/)
  assert.match(annotationPage, /:maxlength="statusEntryMode === 'progress' \? 10000 : 500"/)
  assert.match(annotationPage, /progressDraftSource\.value=null;statusForm\.projectStatus=mode==='progress'[\s\S]*statusForm\.effectiveOn=localDateTimeValue\(\)/)
  assert.match(annotationPage, /progressOnly=statusEntryMode\.value==='progress'/)
})
