<template>
  <div class="talent-detail-content">
    <section v-if="shows('identity')">
      <h4>姓名与联系方式</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="中文姓名">{{ show(detail.chineseName || detail.fullName) }}</el-descriptions-item>
        <el-descriptions-item label="英文姓名">{{ show(detail.englishName) }}</el-descriptions-item>
        <el-descriptions-item label="昵称">{{ show(detail.nickname) }}</el-descriptions-item>
        <el-descriptions-item label="其他名字">{{ show(detail.otherNames) }}</el-descriptions-item>
        <el-descriptions-item label="手机"><SensitiveContactValue :value="detail.primaryPhone" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="备用电话"><SensitiveContactValue :value="detail.secondaryPhone" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="微信"><SensitiveContactValue :value="detail.wechat" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="WhatsApp"><SensitiveContactValue :value="detail.whatsapp" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="邮箱"><SensitiveContactValue :value="detail.primaryEmail" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="备用邮箱"><SensitiveContactValue :value="detail.secondaryEmail" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="Skype"><SensitiveContactValue :value="detail.skype" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="Line"><SensitiveContactValue :value="detail.line" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="其他联系方式" :span="2"><SensitiveContactValue :value="detail.otherContact || detail.contactInfo" :restricted="contactRestricted" /></el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="shows('basic')">
      <h4>基本信息</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="人才编号">{{ show(detail.resourceCode) }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ show(detail.registrationSource) }}</el-descriptions-item>
        <el-descriptions-item label="所在微信">{{ show(detail.wechatAccount) }}</el-descriptions-item>
        <el-descriptions-item label="档案状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
        <el-descriptions-item v-if="showAnnotationWillingness" label="标注意愿">{{ performanceLevelLabel(detail.annotationWillingness) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ show(detail.gender) }}</el-descriptions-item>
        <el-descriptions-item label="年龄">{{ detail.currentAge == null ? '-' : `${detail.currentAge}岁` }}</el-descriptions-item>
        <el-descriptions-item label="出生年月">{{ show(detail.birthYearMonth || detail.birthDate) }}</el-descriptions-item>
        <el-descriptions-item label="国籍 / 民族">{{ join(detail.nationality, detail.ethnicity) }}</el-descriptions-item>
        <el-descriptions-item label="职业状态">{{ employmentLabel(detail.employmentStatus) }}</el-descriptions-item>
        <el-descriptions-item label="当前年级">{{ show(detail.currentStudentGrade) }}</el-descriptions-item>
        <el-descriptions-item label="职业说明" :span="2">{{ show(detail.employmentDetail) }}</el-descriptions-item>
        <el-descriptions-item label="身高">{{ show(detail.height) }}</el-descriptions-item>
        <el-descriptions-item label="容貌">{{ show(detail.appearance) }}</el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="shows('region')">
      <h4>区域信息</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="籍贯">{{ show(detail.ancestralHome) }}</el-descriptions-item>
        <el-descriptions-item label="主要成长地">{{ show(detail.nativePlace) }}</el-descriptions-item>
        <el-descriptions-item label="目前所在地">{{ show(detail.residenceAddress) }}</el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="shows('education')">
      <h4>学历信息</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="最高学历" :span="2">{{ educationLabel(detail.highestEducation) }}</el-descriptions-item>
        <template v-for="item in detail.educationExperiences || []" :key="item.id || `${item.educationLevel}-${item.sortOrder}`">
          <el-descriptions-item :label="educationLevelLabel(item.educationLevel)">{{ show(item.institution) }}</el-descriptions-item>
          <el-descriptions-item label="专业">{{ show(item.major) }}</el-descriptions-item>
          <el-descriptions-item label="院校分类">{{ show(item.institutionCategory) }}</el-descriptions-item>
          <el-descriptions-item label="专业分类">{{ show(item.majorCategory) }}</el-descriptions-item>
          <el-descriptions-item label="毕业年份">{{ show(item.graduationYear) }}</el-descriptions-item>
          <el-descriptions-item label="辅修/学位">{{ join(item.minorMajor, item.degreeName) }}</el-descriptions-item>
        </template>
      </el-descriptions>
    </section>

    <section v-if="shows('language')">
      <h4>语言情况</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item v-for="item in detail.languageSkills || []" :key="item.id" :label="languageRoleLabel(item)">
          {{ item.languageLabel }}<span v-if="item.proficiency"> · {{ proficiencyLabel(item.proficiency) }}</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="!detail.languageSkills?.length" label="语言">-</el-descriptions-item>
        <el-descriptions-item v-if="detail.dialects?.length" label="方言/少数民族语原始登记" :span="2">{{ show(detail.dialects) }}</el-descriptions-item>
      </el-descriptions>
      <h4>证书信息</h4>
      <el-descriptions :column="2" border size="small">
        <template v-for="item in detail.certificates || []" :key="item.id">
          <el-descriptions-item :label="item.certificateType === 'language' ? '外语类证书' : '其他类证书'">{{ item.name }}</el-descriptions-item>
          <el-descriptions-item label="是否发来">{{ item.materialReceived ? '已收到' : '未收到' }}</el-descriptions-item>
        </template>
        <el-descriptions-item v-if="!detail.certificates?.length" label="证书">-</el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="shows('experience')">
      <h4>工作经验</h4>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="标注类经验"><div class="pre-wrap">{{ show(detail.annotationExperience) }}</div></el-descriptions-item>
        <el-descriptions-item label="口译经验"><div class="pre-wrap">{{ show(detail.interpretationExperience) }}</div></el-descriptions-item>
        <el-descriptions-item label="笔译经验"><div class="pre-wrap">{{ show(detail.translationExperience) }}</div></el-descriptions-item>
        <el-descriptions-item label="其他经验"><div class="pre-wrap">{{ show(detail.otherExperience) }}</div></el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="showPerformance && shows('performance')">
      <h4>综合表现</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="总体评价" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.overallScore, detail.overallRating) }}</div></el-descriptions-item>
        <el-descriptions-item label="配合度"><div class="pre-wrap">{{ levelAndNote(detail.cooperationLevel, detail.cooperationNote) }}</div></el-descriptions-item>
        <el-descriptions-item label="守时度"><div class="pre-wrap">{{ levelAndNote(detail.punctualityLevel, detail.punctualityNote) }}</div></el-descriptions-item>
        <el-descriptions-item label="音频标注表现" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.audioAnnotationScore, detail.audioAnnotationEvaluation) }}</div></el-descriptions-item>
        <el-descriptions-item label="非音频标注表现" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.nonAudioAnnotationScore, detail.nonAudioAnnotationEvaluation) }}</div></el-descriptions-item>
        <el-descriptions-item label="采集表现" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.collectionScore, detail.collectionEvaluation) }}</div></el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="section === 'all'">
      <h4>专业能力与评价</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="专业能力">{{ show((detail.capabilityTypes || []).map(capabilityLabel)) }}</el-descriptions-item>
        <el-descriptions-item label="合作形式">{{ show(detail.cooperationType) }}</el-descriptions-item>
        <el-descriptions-item label="笔译语种">{{ show(detail.writtenProfile?.languages) }}</el-descriptions-item>
        <el-descriptions-item label="口译语种">{{ show(detail.interpretationProfile?.languages) }}</el-descriptions-item>
        <el-descriptions-item label="标注语言" :span="2">{{ show((detail.annotationLanguageSkills || []).map(item => item.display)) }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2"><div class="pre-wrap">{{ show(detail.remarks) }}</div></el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="shows('projects') && projects.length">
      <h4>关联项目</h4>
      <el-table :data="projects" border size="small">
        <el-table-column prop="projectType" label="类型" width="90" />
        <el-table-column prop="orderNo" label="订单号" min-width="130" />
        <el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="role" label="角色" width="110" />
        <el-table-column prop="status" label="状态" width="120" />
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SensitiveContactValue from '@/components/common/SensitiveContactValue.vue'

const props = defineProps({
  detail: { type: Object, default: () => ({}) },
  section: { type: String, default: 'all' },
  projects: { type: Array, default: () => [] },
  showPerformance: { type: Boolean, default: true },
  showAnnotationWillingness: { type: Boolean, default: true },
})

const contactRestricted = computed(() => props.detail.contactRestricted === true)

const shows = (section) => props.section === 'all' || props.section === section
const show = (value) => value === null || value === undefined || value === ''
  ? '-'
  : Array.isArray(value) ? (value.join('、') || '-') : value
const join = (...values) => values.filter(Boolean).join(' · ') || '-'
const performanceLevelLabel = value => ({ high: '高', medium: '中', low: '低' }[value] || '')
const scoreAndEvaluation = (score, evaluation) => [score == null ? '' : `${score}分`, String(evaluation || '').trim()].filter(Boolean).join(' · ') || '-'
const levelAndNote = (level, note) => [performanceLevelLabel(level), String(note || '').trim()].filter(Boolean).join(' · ') || '-'
const statusLabel = value => ({ active: '活跃', standby: '备用', inactive: '停用' }[value] || show(value))
const employmentLabel = value => ({ student: '在校学生', employed: '在职', freelance: '自由职业', seeking: '待业/求职中', retired: '已退休', other: '其他' }[value] || show(value))
const educationLabel = value => ({ high_school_or_below: '高中及以下', secondary_vocational: '中专/职高', associate: '专科', bachelor: '本科', master: '硕士研究生', doctor: '博士研究生', other: '其他' }[value] || show(value))
const educationLevelLabel = value => ({ associate: '专科院校', bachelor: '本科院校', second_degree: '第二学位', master: '硕士院校', doctor: '博士院校' }[value] || value)
const languageRoleLabel = item => item.role === 'native' ? '母语' : item.role === 'foreign' ? `第${item.priority || 1}外语` : '方言/民族语言'
const proficiencyLabel = value => ({ very_familiar: '非常熟悉', familiar: '熟悉', basic: '基础交流', listening_mainly: '听懂为主', listening_only: '仅能听懂' }[value] || value)
const capabilityLabel = value => ({ written_translation: '笔译', interpretation: '口译', annotation: '标注' }[value] || value)
</script>

<style scoped>
.talent-detail-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.talent-detail-content section+section{margin-top:16px}.talent-detail-content h4{margin:0 0 8px}.pre-wrap{white-space:pre-wrap;word-break:break-word}
</style>
