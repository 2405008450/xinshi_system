import { reactive } from 'vue'
import { AUTO_DRAFT_DELAY, createAutoDraftStore, draftHash, sanitizeDraft } from './autoDraftStore.js'
const entries = new Set(), managed = new WeakSet()
const recoveryOffered = new Set()
export const autoDraftState = reactive({ records: [], error: '', delay: AUTO_DRAFT_DELAY, lastWriteMs: 0 })
let timer, store, owner = '', installed = false, submitIntent = null, armed = [], armedAt = 0
const userKey = () => localStorage.getItem('user_id') || localStorage.getItem('user_name') || ''
export function markManagedDraft(model) { if (model && typeof model === 'object') managed.add(model) }
function currentStore() {
  const user = userKey()
  if (!user) return null
  if (user !== owner) { owner = user; store = createAutoDraftStore({ storage: localStorage, owner }); autoDraftState.records = store.list() }
  return store
}
export function refreshAutoDrafts() { autoDraftState.records = currentStore()?.list() || [] }
function root(entry) { const el = entry.vm.$el; return el?.nodeType === 1 ? el : null }
function model(entry) { return entry.kind === 'form' ? entry.vm.$props.model || entry.vm.$attrs.model : entry.vm.$props.modelValue }
function excluded(entry) {
  const el = root(entry), props = entry.vm.$props, attrs = entry.vm.$attrs
  return !el || !el.isConnected || !el.getClientRects().length || !userKey() || location.pathname === '/login' || managed.has(model(entry)) || !!el.closest('[data-auto-draft="off"],.search-form,.search-bar,.search-area,.filter-bar,.chat-composer,.project-chat-panel,.group-composer,.discussion-chat__composer,.el-message-box,.el-select-dropdown,.el-picker-panel') || props.disabled || attrs.disabled === '' || attrs.disabled === true || props.readonly || attrs.readonly === '' || attrs.readonly === true || props.type === 'password' || /密码|口令|密钥|验证码|password|token|secret/i.test(String(attrs['aria-label']||'')+' '+String(attrs.placeholder||props.placeholder||'')) || /password|current-password|new-password|one-time-code/i.test(String(attrs.autocomplete || '')) || /^搜索|^筛选/.test(String(attrs.placeholder || props.placeholder || ''))
}
function context(entry) {
  const el = root(entry), value = model(entry), path = location.pathname + location.hash
  const dialog = el?.closest('.el-dialog'), title = dialog?.querySelector('.el-dialog__title,.dialog-field-search-header__title')?.textContent?.trim() || document.title || '编辑内容'
  const field = el?.closest('.el-form-item')?.querySelector('.el-form-item__label')?.textContent?.trim() || entry.vm.$attrs['aria-label'] || entry.vm.$attrs.placeholder || entry.vm.$props.placeholder || entry.vm.$options.name || '编辑框'
  let record = value && typeof value === 'object' ? value.id || value.orderNo || value.order_no || value.clientCode : ''
  const rowKeys = []
  for (let vm = entry.vm.$; vm; vm = vm.parent) {
    const state = vm.setupState || {}
    record ||= state.editingId || state.editId || state.recordId || state.currentRecordId || state.editingOrderNo || ''
    if (vm.vnode?.key != null) rowKeys.push(String(vm.vnode.key))
  }
  const same = entry.kind==='form'&&!record?[...entries].filter(item => item.kind === entry.kind && root(item)?.closest('.el-dialog') === dialog && (item.vm.$options.name || '') === (entry.vm.$options.name || '')):[]
  const index = entry.kind === 'form' ? same.indexOf(entry) : [...(dialog || document).querySelectorAll('input,textarea,[contenteditable="true"]')].indexOf(el?.querySelector?.('input,textarea,[contenteditable="true"]') || el)
  const identity = [path, title, entry.kind, String(record || 'new'), rowKeys.join('/'), entry.kind === 'form' ? (record?'':index) : `${field}:${rowKeys.length?'':index}`].join('|')
  return { id: `${draftHash(identity)}:${identity}`, route: path, title: entry.kind === 'form' ? title : `${title} · ${field}`, record: String(record || '新建'), identity }
}
function effectiveEntries(target) {
  const matches = [...entries].filter(entry => root(entry)?.contains(target) && !excluded(entry))
  const forms = matches.filter(entry => entry.kind === 'form')
  if (forms.length) return [forms.find(item => item.vm.$options.name === 'AppForm') || forms[forms.length - 1]]
  // 已有专用草稿的表单不重复保存其子输入框。
  if ([...entries].some(entry => entry.kind === 'form' && managed.has(model(entry)) && root(entry)?.contains(target))) return []
  return matches.filter(entry => !matches.some(parent => parent !== entry && root(parent) !== root(entry) && root(parent)?.contains(root(entry))))
}
function snapshot(entry) {
  if (excluded(entry)) return null
  const info = context(entry), data = sanitizeDraft(model(entry))
  if (data === undefined) return null
  return { ...info, data }
}
function flush() {
  clearTimeout(timer); timer = null
  if (![...entries].some(entry=>entry.dirty)) return
  const storage = currentStore(); if (!storage) return
  const started = performance.now()
  for (const entry of entries) {
    if (!entry.dirty || entry.recoveryPending || entry.owner !== userKey()) continue
    const value = snapshot(entry) || (entry.native ? entry.lastSnapshot : null); if (!value) { entry.dirty = false; continue }
    try {
      if (JSON.stringify(value.data) === entry.baseline) { if (storage.get(value.id)) storage.remove(value.id); entry.dirty = false; continue }
      storage.save(value); entry.dirty = false; autoDraftState.error = ''
    } catch (error) { autoDraftState.error = `本机草稿未能保存：${error.message || '浏览器存储空间不足'}` }
  }
  refreshAutoDrafts(); autoDraftState.lastWriteMs = performance.now() - started
  // 只在实测一次写入超过50毫秒时延长，避免大表单频繁阻塞界面。
  autoDraftState.delay = autoDraftState.lastWriteMs > 50 ? 2000 : AUTO_DRAFT_DELAY
}
function touched(event) {
  const target = event.target
  if (!target?.closest || target.closest('.auto-draft-center')) return
  let matching = effectiveEntries(target)
  if (!matching.length && target.matches('input,textarea,select,[contenteditable="true"]') && !target.disabled && !target.readOnly && !['password','hidden','file','button','submit'].includes(target.type) && ![...entries].some(entry=>entry.kind==='form'&&managed.has(model(entry))&&root(entry)?.contains(target))) {
    let native=[...entries].find(entry=>entry.native&&root(entry)===target)
    if(!native){
      const read=()=>target.isContentEditable?target.textContent:target.type==='checkbox'?target.checked:target.multiple?[...target.selectedOptions].map(option=>option.value):target.value
      const props={get modelValue(){return read()},type:target.type,disabled:target.disabled,readonly:target.readOnly}
      const vm={$el:target,$props:props,$attrs:{'aria-label':target.getAttribute('aria-label'),placeholder:target.placeholder,autocomplete:target.autocomplete},$options:{name:'NativeEditor'},$emit:(_,value)=>{if(target.isContentEditable)target.textContent=value;else if(target.type==='checkbox')target.checked=value;else target.value=value;target.dispatchEvent(new Event('input',{bubbles:true}));target.dispatchEvent(new Event('change',{bubbles:true}))}}
      native={vm,kind:'control',native:true,dirty:false,owner:userKey()};entries.add(native)
    }
    if(!excluded(native))matching=[native]
  }
  if (!matching.length && Date.now() - armedAt < 60000 && target.closest('.el-popper,.el-picker-panel,.el-select-dropdown')) matching = armed.filter(entry => entries.has(entry) && !excluded(entry))
  if (matching.length) { armed = matching; armedAt = Date.now() }
  for (const entry of matching) {
    const info = context(entry)
    if (entry.contextId !== info.id) { entry.contextId = info.id; entry.baseline = JSON.stringify(sanitizeDraft(model(entry))) }
    const offerKey=`${userKey()}:${info.id}`
    if((event.type==='focusin'||event.type==='click')&&!recoveryOffered.has(offerKey)){
      recoveryOffered.add(offerKey)
      const saved=currentStore()?.get(info.id)
      if(saved&&JSON.stringify(saved.data)!==JSON.stringify(sanitizeDraft(model(entry)))){
        entry.recoveryPending=true
        window.dispatchEvent(new CustomEvent('auto-draft-available',{detail:{id:info.id}}))
      }
    }
    if(entry.recoveryPending){if(['input','change','drop'].includes(event.type))entry.recoveryPending=false;else continue}
    if(event.type!=='focusin')entry.dirty=true; entry.owner = userKey()
    if(!entry.native&&!entry.stopWatch){
      entry.stopWatch=entry.vm.$watch(()=>model(entry),()=>{
        if(entry.recoveryPending||excluded(entry)||entry.owner!==userKey()||context(entry).id!==entry.contextId)return
        entry.dirty=true;clearTimeout(timer);timer=setTimeout(flush,autoDraftState.delay)
      },{deep:entry.kind==='form'||typeof model(entry)==='object',flush:'post'})
    }
    if(entry.native)entry.lastSnapshot=snapshot(entry)
  }
  if (event.type === 'click') {
    const button = target.closest('button'), text = button?.textContent?.trim() || button?.getAttribute('aria-label') || ''
    if ((button?.closest('.el-dialog') && /^(取消|关闭|完成|返回)|关闭窗口/.test(text)) || (!target.closest('.el-dialog') && target.closest('.el-overlay,.el-overlay-dialog'))) flush()
    if (/^(保存|确定|提交|发送|确认保存)/.test(text)) {
      const scope = button.closest('.el-dialog') || button.closest('form') || button.closest('.inline-text-field')
      submitIntent = { time: Date.now(), entries: [...entries].filter(entry => !excluded(entry) && scope?.contains(root(entry))) }
    }
  }
  if(matching.length){clearTimeout(timer); timer = setTimeout(flush, autoDraftState.delay)}
}
export function draftSubmitSnapshot(url = '') {
  if (!submitIntent || Date.now() - submitIntent.time > 2000 || /upload|image|screenshot|auth|notification|chat|conversation/i.test(url)) return null
  return submitIntent.entries.map(entry => ({ entry, value: snapshot(entry) })).filter(item => item.value)
}
export function completeDraftSubmit(records) {
  if (!records) return
  const storage = currentStore(); if (!storage) return
  for (const { entry, value } of records) {
    const current = snapshot(entry)
    if (current && JSON.stringify(current.data) !== JSON.stringify(value.data)) continue
    try { storage.remove(value.id); entry.dirty = false; entry.baseline = JSON.stringify(value.data);entry.stopWatch?.();entry.stopWatch=null } catch { /* 不影响业务保存 */ }
  }
  submitIntent = null; refreshAutoDrafts()
}
export function discardAutoDraft(id) { currentStore()?.remove(id);for(const entry of entries)if(context(entry).id===id)entry.recoveryPending=false; refreshAutoDrafts() }
export function restoreAutoDraft(id) {
  const record = currentStore()?.get(id)
  if (!record) return false
  const entry = [...entries].find(item => !excluded(item) && context(item).id === id)
  if (!entry) return false
  entry.recoveryPending=false
  const data = sanitizeDraft(record.data)
  if (entry.kind === 'form') Object.assign(model(entry), data)
  else entry.vm.$emit('update:modelValue', data)
  entry.dirty = true; entry.owner = userKey(); clearTimeout(timer); timer = setTimeout(flush, autoDraftState.delay)
  return true
}
export function installAutoDrafts(app) {
  app.mixin({
    mounted() {
      const name = this.$options.name || '', props = this.$props, attrs = this.$attrs
      const form = props.model || attrs.model
      if (/Dialog|Drawer|Popover|Tooltip|Transfer|Table|Upload|InlineTextField/.test(name)) return
      const kind = form && typeof form === 'object' && /Form$/.test(name) ? 'form' : this.$.vnode.props?.['onUpdate:modelValue'] && 'modelValue' in props ? 'control' : ''
      if (!kind || props.type === 'password') return
      const entry = { vm: this, kind, dirty: false, owner: userKey() }
      this.$.__autoDraftEntry = entry; entries.add(entry)
    },
    beforeUnmount() {
      const entry = this.$.__autoDraftEntry
      if (!entry) return
      if (entry.dirty) flush()
      entry.stopWatch?.()
      entries.delete(entry)
    },
  })
  if (installed) return
  installed = true
  for (const type of ['input', 'change', 'click', 'focusin', 'drop']) document.addEventListener(type, touched, true)
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){flush();return}
    if(event.key!=='Enter'||event.isComposing||(event.target.tagName==='TEXTAREA'&&!event.ctrlKey))return
    const scope=event.target.closest?.('.inline-text-field,form,.el-dialog')
    if(scope)submitIntent={time:Date.now(),entries:[...entries].filter(entry=>!excluded(entry)&&scope.contains(root(entry)))}
  },true)
  window.addEventListener('pagehide', flush)
  document.addEventListener('visibilitychange', () => { if (document.hidden) flush() })
  window.addEventListener('storage', refreshAutoDrafts)
  new MutationObserver(()=>{for(const entry of entries)if(entry.native&&!root(entry)?.isConnected){if(entry.dirty)flush();entries.delete(entry)}}).observe(document.body,{childList:true,subtree:true})
  refreshAutoDrafts()
}
