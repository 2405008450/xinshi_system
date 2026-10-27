<template>
  <div class="resource-custom-accounts">
    <div v-for="(account, index) in modelValue" :key="index" class="resource-custom-account" data-dialog-field-search-group>
      <span hidden data-dialog-field-search-group-title>自定义账号 {{ index + 1 }}</span>
      <el-form-item label="账号名称" :prop="`${propPrefix}.${index}.name`" :rules="nameRules(index)">
        <el-input :model-value="account.name" :disabled="disabled" maxlength="50" placeholder="如 Telegram、Skype" @update:model-value="update(index, 'name', $event)" />
      </el-form-item>
      <el-form-item :label="`资源${account.name || '**'}号`" :prop="`${propPrefix}.${index}.value`" :rules="[{ required: true, whitespace: true, message: '请填写账号', trigger: 'blur' }]">
        <el-input :model-value="account.value" :disabled="disabled" maxlength="100" placeholder="请输入资源账号" @update:model-value="update(index, 'value', $event)" />
      </el-form-item>
      <el-button link type="danger" :disabled="disabled" @click="emit('update:modelValue', modelValue.filter((_, i) => i !== index))">移除</el-button>
    </div>
    <el-button :disabled="disabled || modelValue.length >= 30" @click="emit('update:modelValue', [...modelValue, { name: '', value: '' }])">增加自定义资源账号</el-button>
  </div>
</template>
<script setup>
const props = defineProps({ modelValue: { type: Array, default: () => [] }, propPrefix: { type: String, default: 'custom_accounts' }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
function update(index, key, value) { emit('update:modelValue', props.modelValue.map((item, i) => i === index ? { ...item, [key]: value } : item)) }
const normalize = value => (value || '').trim().toLocaleLowerCase()
const nameRules = index => [
  { required: true, whitespace: true, message: '请填写账号名称', trigger: 'blur' },
  { validator: (_rule, value, done) => {
    const name = normalize(value)
    if (/^(资源)?what(s)?app(号)?$/i.test(name)) return done(new Error('请填写独立的 WhatsApp 号字段'))
    done(props.modelValue.some((item, i) => i !== index && normalize(item.name) === name) ? new Error('账号名称不能重复') : undefined)
  }, trigger: 'blur' },
]
</script>
<style scoped>
.resource-custom-accounts{width:100%;min-width:260px}
.resource-custom-account{display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap}
.resource-custom-account>.el-form-item{flex:1 1 130px;min-width:0}
.resource-custom-account>.el-button{margin-top:30px}
</style>
