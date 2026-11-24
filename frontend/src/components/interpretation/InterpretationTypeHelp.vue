<template>
  <el-popover trigger="click" placement="bottom-end" width="min(700px, calc(100vw - 32px))"
    title="口译项目类型说明" :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }] }">
    <template #reference><el-button link type="primary" size="small" @click.stop>类型说明</el-button></template>
    <div class="interpretation-type-help">
      <section class="interpretation-type-comparison">
        <h4>小型会议口译与会议交传口译的异同</h4>
        <p><strong>相同点：</strong>都采用分段交替传译：发言人讲完一段后暂停，由译员翻译，再继续发言。</p>
        <p><strong>主要区别：</strong></p>
        <ol>
          <li><strong>发言场景与现场压力：</strong>正式会议交传中，发言人与译员通常在主席台、讲台等位置，面向全体参会者发言，对译员的公开表达和临场应变要求更高，现场压力也相对较大。</li>
          <li><strong>会议规模：</strong>正式会议交传常见于约20人以上的会议；小型会议则以人数较少、便于直接交流的场景为主。人数仅供参考，分类还需结合会议形式及正式程度。</li>
          <li><strong>互动方式与氛围：</strong>小型商务会议通常互动较多、氛围相对轻松，译员遇到未听清或不明确的内容时，可以适时询问、核实；正式会议交传更注重发言节奏与现场秩序，需要澄清时也应选择适当时机。</li>
        </ol>
      </section>
      <p>按主要场景和传译方式选择，可多选；具体工作内容请填写在“具体任务”。</p>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-for="item in projectTypeOptions" :key="item.value" :label="item.label">
          {{ projectTypeDescriptions[item.value] }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </el-popover>
</template>

<script setup>
import { projectTypeOptions, projectTypeDescriptions } from '@/utils/interpretationProjectDetail'
</script>

<style scoped>
.interpretation-type-help { max-height: min(520px, calc(100vh - 180px)); overflow-y: auto; overflow-wrap: anywhere; }
.interpretation-type-help p { margin: 8px 0 12px; color: var(--el-text-color-secondary); }
.interpretation-type-comparison { padding-bottom: 12px; border-bottom: 1px solid var(--el-border-color-lighter); line-height: 1.7; }
.interpretation-type-comparison h4 { margin: 8px 0 12px; font-size: 14px; }
.interpretation-type-comparison ol { margin: 0; padding-left: 22px; }
.interpretation-type-comparison li { margin-bottom: 8px; }
</style>
