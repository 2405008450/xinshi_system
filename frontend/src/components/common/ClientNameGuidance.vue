<template>
  <div v-if="compact" class="client-name-guidance client-name-guidance--compact">
    <span>企业简称建议：行政区划＋字号＋行业</span>
    <el-tooltip content="例如：广州信实翻译服务有限公司 → 广州信实翻译。公司客户填写公司名称，个人姓名填写在客户联系人；个人客户的全称与简称一般保持一致。" placement="top" :show-after="200"><el-button link type="primary">填写说明</el-button></el-tooltip>
  </div>
  <div v-else class="client-name-guidance">
    <div>企业客户简称建议采用：行政区划＋字号＋行业表述。</div>
    <div>例如：广州信实翻译服务有限公司 → 广州信实翻译（“服务”二字可省略）。</div>
    <div>有公司名称时应尽量填写公司名称；个人姓名请填写在“客户联系人”。个人客户的全称与简称一般保持一致。</div>
  </div>
</template>

<script setup>
defineProps({compact:Boolean})
</script>

<style scoped>
.client-name-guidance {
  width: 100%;
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.client-name-guidance--compact { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 12px; }
</style>
