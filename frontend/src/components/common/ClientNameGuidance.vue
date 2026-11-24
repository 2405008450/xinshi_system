<template>
  <div class="client-name-guidance">
    <span class="client-name-guidance__summary">企业简称：行政区划＋字号＋行业</span>
    <el-popover trigger="click" placement="bottom-end" width="min(600px, calc(100vw - 32px))"
      title="客户名称填写说明" :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }] }">
      <template #reference><el-button link type="primary" size="small" @click.stop>填写说明</el-button></template>
      <div class="client-name-guidance__details">
        <p v-if="createOnSave">没有匹配客户时，填写客户全称及简称后，保存项目会自动新增客户。</p>
        <p>企业客户简称建议采用：行政区划＋字号＋行业表述。</p>
        <p>例如：广州信实翻译服务有限公司 → 广州信实翻译（“服务”二字可省略）。</p>
        <p>有公司名称时应尽量填写公司名称；个人姓名请填写在“客户联系人”。个人客户的全称与简称一般保持一致。</p>
      </div>
    </el-popover>
  </div>
</template>

<script setup>
defineProps({createOnSave:Boolean})
</script>

<style scoped>
.client-name-guidance {
  width: 100%;
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
  overflow-wrap: anywhere;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.client-name-guidance__summary { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.client-name-guidance > .el-button { flex-shrink: 0; }
.client-name-guidance__details { max-height: min(400px, calc(100vh - 180px)); overflow-y: auto; overflow-wrap: anywhere; line-height: 1.7; }
.client-name-guidance__details p { margin: 8px 0; }
</style>
