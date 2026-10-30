<template>
  <div class="talent-detail-content" :class="{'is-dialog-content':inDialog}"><el-tabs v-model="resumeTab" :class="{'resume-tabs-summary':section!=='all'}"><el-tab-pane label="中文简历" name="zh"><CollapsibleSections ref="sectionPanels" :reset-key="`${detail.id||''}:${section}`">
    <template v-if="section==='all'" #actions><TalentResumeYear :model-value="resumeProfile.resumeYear" readonly /></template>
    <el-alert v-if="detail.archivedIntoId" title="此档案已归档，原资料只读，历史业务关联保留。" type="info" :closable="false">
      <template #default><el-button link type="primary" @click="openRetained">打开保留档案</el-button></template>
    </el-alert>
    <el-collapse-item v-if="shows('identity')" name="detail-section-1" data-section-key="detail-section-1" title="姓名与联系方式"><section v-if="shows('identity')">
      <h4>姓名与联系方式</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="中文姓名">{{ show(detail.chineseName || detail.fullName) }}</el-descriptions-item>
        <el-descriptions-item label="外文姓名">{{ show(detail.englishName) }}</el-descriptions-item>
        <el-descriptions-item label="昵称">{{ show(detail.nickname) }}</el-descriptions-item>
        <el-descriptions-item label="其他名字">{{ show(detail.otherNames) }}</el-descriptions-item>
        <el-descriptions-item label="身份证号码" :span="2"><SensitiveContactValue :value="detail.identityNumber" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="手机"><SensitiveContactValue :value="detail.primaryPhone" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="备用电话"><SensitiveContactValue :value="detail.secondaryPhone" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="微信"><SensitiveContactValue :value="detail.wechat" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="WhatsApp"><SensitiveContactValue :value="detail.whatsapp" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="邮箱"><SensitiveContactValue :value="detail.primaryEmail" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="备用邮箱"><SensitiveContactValue :value="detail.secondaryEmail" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="Skype"><SensitiveContactValue :value="detail.skype" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="Line"><SensitiveContactValue :value="detail.line" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="其他联系方式" :span="2"><SensitiveContactValue :value="detail.otherContact || detail.contactInfo" :restricted="contactRestricted" /></el-descriptions-item>
        <el-descriptions-item label="可联系时段" :span="2">{{ contactAvailabilityLabel(detail.contactAvailability) }}<span v-if="detail.contactAvailability">（{{ detail.residenceTimezone || '所在地时区未登记' }}）</span></el-descriptions-item>
      </el-descriptions>
      <el-descriptions v-if="!contactRestricted && detail.inheritedContacts?.length" :column="1" border size="small" class="inherited-details">
        <el-descriptions-item v-for="(contact,index) in detail.inheritedContacts" :key="index" :label="`${contact.sourceCode || contact.sourceId.slice(0,8)} · ${contact.label}`"><SensitiveContactValue :value="contact.value" :restricted="false" /></el-descriptions-item>
      </el-descriptions>
      <div v-if="detail.inheritedAttachments?.length" class="inherited-details">
        <h4>来源附件（只读）</h4>
        <div v-for="attachment in detail.inheritedAttachments" :key="attachment.id"><el-button link type="primary" @click="downloadInherited(attachment)">{{ attachment.originalName }}</el-button><span> · {{ attachment.sourceCode || attachment.sourceId.slice(0,8) }}</span></div>
      </div>
    </section></el-collapse-item>

    <el-collapse-item v-if="shows('basic')" name="detail-section-2" data-section-key="detail-section-2" title="基本信息"><section v-if="shows('basic')">
      <h4>基本信息</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="人才编号">{{ show(detail.resourceCode) }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ show(detail.operatorName) }}</el-descriptions-item>
        <el-descriptions-item label="操作时间">{{ formatOperationTime(detail.operatedAt) }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ show(detail.registrationSource) }}</el-descriptions-item>
        <el-descriptions-item label="所在微信">{{ formatWechatAccounts(detail.wechatAccounts, detail.wechatAccount) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="所在企微小群"><div class="pre-wrap">{{ show(detail.wechatGroups) }}</div></el-descriptions-item>
        <el-descriptions-item label="企微小群状态">{{ show(detail.wecomSmallGroupStatus) }}</el-descriptions-item>
        <el-descriptions-item label="所在企微大群"><div class="pre-wrap">{{ show(detail.wecomLargeGroups) }}</div></el-descriptions-item>
        <el-descriptions-item label="企微大群状态">{{ show(detail.wecomLargeGroupStatus) }}</el-descriptions-item>
        <el-descriptions-item label="档案状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
        <el-descriptions-item v-if="showAnnotationWillingness" label="标注意愿">{{ performanceLevelLabel(detail.annotationWillingness) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ show(detail.gender) }}</el-descriptions-item>
        <el-descriptions-item label="视力">{{ show(detail.eyesight) }}</el-descriptions-item>
        <el-descriptions-item label="年龄">{{ detail.currentAge == null ? '-' : `${detail.currentAge}岁${!detail.birthYearMonth && !detail.birthDate ? '（登记年龄）' : ''}` }}</el-descriptions-item>
        <el-descriptions-item label="出生年月">{{ show(detail.birthYearMonth || detail.birthDate) }}</el-descriptions-item>
        <el-descriptions-item label="国籍 / 民族">{{ join(detail.nationality, detail.ethnicity) }}</el-descriptions-item>
        <el-descriptions-item label="职业状态">{{ employmentLabel(detail.employmentStatus) }}</el-descriptions-item>
        <el-descriptions-item label="当前年级">{{ show(detail.currentStudentGrade) }}</el-descriptions-item>
        <el-descriptions-item label="职业说明" :span="2">{{ show(detail.employmentDetail) }}</el-descriptions-item>
        <el-descriptions-item label="身高">{{ show(detail.height) }}</el-descriptions-item>
        <el-descriptions-item label="容貌">{{ show(detail.appearance) }}</el-descriptions-item>
      </el-descriptions>
    </section></el-collapse-item>

    <el-collapse-item v-if="shows('region')" name="detail-section-3" data-section-key="detail-section-3" title="区域信息"><section v-if="shows('region')">
      <h4>区域信息</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="籍贯">{{ show(detail.ancestralHome) }}</el-descriptions-item>
        <el-descriptions-item label="主要成长地">{{ show(detail.nativePlace) }}</el-descriptions-item>
        <el-descriptions-item label="目前所在地">{{ show(detail.residenceAddress) }}</el-descriptions-item>
        <el-descriptions-item label="时区">{{ show(detail.residenceTimezone) }}</el-descriptions-item>
      </el-descriptions>
    </section></el-collapse-item>

    <el-collapse-item v-if="shows('education')" name="detail-section-4" data-section-key="detail-section-4" title="学历信息"><section v-if="shows('education')">
      <h4>学历信息</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="最高学历" :span="2">{{ educationLabel(detail.highestEducation) }}</el-descriptions-item>
        <el-descriptions-item label="本科毕业年份" :span="2">{{ show(detail.educationExperiences?.find(item=>item.educationLevel==='bachelor')?.graduationYear) }}</el-descriptions-item>
        <template v-for="item in detail.educationExperiences || []" :key="item.id || `${item.educationLevel}-${item.sortOrder}`">
          <el-descriptions-item :label="educationLevelLabel(item.educationLevel)">{{ show(item.institution) }}</el-descriptions-item>
          <el-descriptions-item label="专业">{{ show(item.major) }}</el-descriptions-item>
          <el-descriptions-item label="院校分类">{{ show(item.institutionCategory) }}</el-descriptions-item>
          <el-descriptions-item label="专业分类">{{ show(item.majorCategory) }}</el-descriptions-item>
          <el-descriptions-item label="毕业年份">{{ show(item.graduationYear) }}</el-descriptions-item>
          <el-descriptions-item label="辅修/学位">{{ join(item.minorMajor, item.degreeName) }}</el-descriptions-item>
        </template>
      </el-descriptions>
    </section></el-collapse-item>

    <el-collapse-item v-if="shows('language')" name="detail-section-5" data-section-key="detail-section-5" title="语言情况"><section v-if="shows('language')">
      <h4>语言情况</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item v-for="item in displayLanguageSkills" :key="item.id" :label="languageRoleLabel(item)">
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
    </section></el-collapse-item>

    <el-collapse-item v-if="shows('education')" name="detail-education-experience" data-section-key="detail-education-experience" title="教育经历"><ResumeExperienceGrid :model-value="educationRows" education canonical-education readonly group-title="教育经历" /></el-collapse-item>
    <el-collapse-item v-if="shows('experience')" name="detail-internships" data-section-key="detail-internships" title="实习经历"><ResumeExperienceGrid :model-value="resumeProfile.internships" readonly group-title="实习经历" /></el-collapse-item>
    <el-collapse-item v-if="shows('experience')" name="detail-section-6" data-section-key="detail-section-6" title="工作经验"><el-collapse-item v-for="group in resumeWorkGroups" :key="group.key" :name="`detail-work-${group.key}`" :data-section-key="`detail-work-${group.key}`" :title="group.label"><ResumeExperienceGrid :model-value="resumeProfile[group.key]" readonly :group-title="group.label" :interpretation="group.key=== 'interpretation'" :annotation="group.key=== 'annotation'" /></el-collapse-item></el-collapse-item>

    <el-collapse-item v-if="showPerformance && shows('performance')" name="detail-section-7" data-section-key="detail-section-7" title="综合表现"><section v-if="showPerformance && shows('performance')">
      <h4>综合表现</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="人才分级" :span="2">{{ talentGradeLabel(detail.talentGrade) }}<TalentEvaluationMeta :evaluation="detail" group-key="talent_grade" /></el-descriptions-item>
        <el-descriptions-item label="配合度"><div class="pre-wrap">{{ levelAndNote(detail.cooperationLevel, detail.cooperationNote) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="cooperation" /></el-descriptions-item>
        <el-descriptions-item label="守时度"><div class="pre-wrap">{{ levelAndNote(detail.punctualityLevel, detail.punctualityNote) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="punctuality" /></el-descriptions-item>
      </el-descriptions>
      <el-collapse-item name="detail-domain-annotation" data-section-key="detail-domain-annotation" title="标注"><h5>标注</h5><TalentMediaSamples :person-id="detail.id" category="annotation_sample" :attachments="detail.attachments || []" />
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="总体评价" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.overallScore, detail.overallRating) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="overall" /></el-descriptions-item>
        <el-descriptions-item label="音频标注表现" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.audioAnnotationScore, detail.audioAnnotationEvaluation) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="audio_annotation" /></el-descriptions-item>
        <el-descriptions-item label="非音频标注表现" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.nonAudioAnnotationScore, detail.nonAudioAnnotationEvaluation) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="non_audio_annotation" /></el-descriptions-item>
        <el-descriptions-item label="采集表现" :span="2"><div class="pre-wrap">{{ scoreAndEvaluation(detail.collectionScore, detail.collectionEvaluation) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="collection" /></el-descriptions-item>
      </el-descriptions></el-collapse-item>
      <el-collapse-item name="detail-domain-interpretation" data-section-key="detail-domain-interpretation" title="口译"><h5>口译</h5><TalentMediaSamples :person-id="detail.id" category="interpretation_sample" :attachments="detail.attachments || []" />
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="口译员评级" :span="2">{{ interpretationRatingLabel(detail.interpretationRating) }}<div class="rating-hint">{{ interpretationRatingHint }}</div><TalentEvaluationMeta :evaluation="detail" group-key="interpretation" /></el-descriptions-item>
        <el-descriptions-item label="说明" :span="2"><div class="pre-wrap">{{ show(detail.interpretationRatingNote) }}</div></el-descriptions-item>
        <el-descriptions-item label="口译领域" :span="2"><div class="pre-wrap">{{ show(detail.interpretationDomains) }}</div></el-descriptions-item>
      </el-descriptions></el-collapse-item>
      <el-collapse-item name="detail-domain-written" data-section-key="detail-domain-written" title="笔译"><h5>笔译</h5><div>常用CAT经验：{{resumeProfile.catTools.join("、")||"-"}}</div>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="总体评价">{{ detail.writtenTranslationScore == null ? '-' : `${detail.writtenTranslationScore}分` }}</el-descriptions-item>
        <el-descriptions-item label="具体评价"><div class="pre-wrap">{{ show(detail.writtenTranslationEvaluation) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="written_translation" /></el-descriptions-item>
      </el-descriptions></el-collapse-item>
    </section></el-collapse-item>

    <el-collapse-item v-if="section === 'all'" name="detail-section-8" data-section-key="detail-section-8" title="专业能力与评价"><section v-if="section === 'all'">
      <h4>专业能力与评价</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="专业能力">{{ show((detail.capabilityTypes || []).map(capabilityLabel)) }}</el-descriptions-item>
        <el-descriptions-item label="合作形式">{{ show(detail.cooperationType) }}</el-descriptions-item>
        <el-descriptions-item label="笔译语种">{{ show(detail.writtenProfile?.languages) }}</el-descriptions-item>
        <el-descriptions-item label="口译语种">{{ show(detail.interpretationProfile?.languages) }}</el-descriptions-item>
        <el-descriptions-item label="标注语言" :span="2">{{ show((detail.annotationLanguageSkills || []).map(item => item.display)) }}</el-descriptions-item>
        <el-descriptions-item v-if="showPerformance && detail.writtenProfile" label="笔译质量评分" :span="2">{{ show(detail.writtenProfile.qualityScore) }}<TalentEvaluationMeta :evaluation="detail" group-key="written_profile" /></el-descriptions-item>
        <el-descriptions-item v-if="showPerformance && detail.interpretationProfile" label="口译能力评价" :span="2"><div class="pre-wrap">{{ join(detail.interpretationProfile.interpretationLevel, detail.interpretationProfile.qualityScore, detail.interpretationProfile.evaluationSummary) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="interpretation_profile" /></el-descriptions-item>
        <el-descriptions-item v-if="showPerformance && detail.annotationProfile" label="标注能力评价" :span="2"><div class="pre-wrap">{{ join(detail.annotationProfile.qualityScore, detail.annotationProfile.remarks) }}</div><TalentEvaluationMeta :evaluation="detail" group-key="annotation_profile" /></el-descriptions-item>
        <el-descriptions-item label="备注" :span="2"><div class="pre-wrap">{{ show(detail.remarks) }}</div></el-descriptions-item>
      </el-descriptions>
    </section></el-collapse-item>

    <el-collapse-item v-if="section==='all'" name="detail-photos" data-section-key="detail-photos" title="照片与音频"><el-descriptions :column="1" border size="small"><el-descriptions-item v-for="category in photoDetailCategories" :key="category" :label="photoAttachmentLabel(category)"><template v-for="item in (detail.attachments||[]).filter(file=>file.category===category)" :key="item.id"><el-button link type="primary" @click="downloadInherited({...item,sourceId:detail.id})">{{item.originalName}}</el-button></template><span v-if="!(detail.attachments||[]).some(file=>file.category===category)">-</span></el-descriptions-item></el-descriptions></el-collapse-item>
    <el-collapse-item v-if="!contactRestricted && section==='all'" name="detail-settlement" data-section-key="detail-settlement" title="商务与结算"><section><h4>商务与结算</h4><TalentSettlementDetail :value="detail.settlement" /></section></el-collapse-item>
    <el-collapse-item v-if="shows('projects')" name="detail-section-9" data-section-key="detail-section-9" title="项目情况"><section v-if="shows('projects')">
      <h4>项目情况</h4>
      <el-alert v-if="projectsError" :title="projectsError" type="error" :closable="false"><el-button link @click="$emit('reload-projects')">重试</el-button></el-alert>
      <el-table v-else :data="projects" v-loading="projectsLoading" border size="small" empty-text="暂无关联项目">
        <el-table-column prop="projectType" label="类型" width="90" />
        <el-table-column prop="orderNo" label="订单号" min-width="130" />
        <el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="role" label="角色" width="110" />
        <el-table-column prop="status" label="状态" width="120" />
      </el-table>
    </section></el-collapse-item>
  </CollapsibleSections></el-tab-pane><el-tab-pane v-if="section==='all'" label="英文简历 / English" name="en"><LocalizedResumeEditor :model-value="localizedVersion" locale="en" readonly /></el-tab-pane><el-tab-pane v-if="section==='all'" label="外文简历" name="foreign"><el-select v-model="foreignResumeLocale" filterable><el-option v-for="language in foreignResumeLanguages" :key="language.value" :label="language.label" :value="language.value" /></el-select><LocalizedResumeEditor :key="foreignResumeLocale" :model-value="localizedVersion" :locale="foreignResumeLocale" readonly /></el-tab-pane></el-tabs></div>
</template>

<script setup>
import { computed,ref,watch } from 'vue'
import ResumeExperienceGrid from './ResumeExperienceGrid.vue'
import LocalizedResumeEditor from './LocalizedResumeEditor.vue'
import {resumeProfileForm,educationFormRows,emptyResumeVersion} from '@/utils/talentResumeProfile'
import {foreignResumeLanguages} from '@/utils/talentResumeLocales'
import {photoAttachmentLabel} from '@/utils/talentPhotoCategories'
const photoDetailCategories=['id_photo','life_photo','photo','audio']
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTalentAttachmentBlob } from '@/api/talents'
const router = useRouter()
function openRetained() { router.push({ name: 'Talents', query: { openTalent: props.detail.archivedIntoId } }) }
async function downloadInherited(attachment) {
  try { const blob = await getTalentAttachmentBlob(attachment.sourceId, attachment.id); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = attachment.originalName; link.click(); setTimeout(() => URL.revokeObjectURL(url), 10000) }
  catch { ElMessage.error('来源附件读取失败') }
}
import { formatWechatAccounts } from '@/utils/companyWechatAccounts'
import SensitiveContactValue from '@/components/common/SensitiveContactValue.vue'
import { normalizeForeignLanguagePriorities } from '@/utils/talentLanguageSkills'
import { talentStatusLabel } from '@/utils/talentStatus'
import CollapsibleSections from '@/components/common/CollapsibleSections.vue'
import TalentResumeYear from './TalentResumeYear.vue'
import TalentEvaluationMeta from './TalentEvaluationMeta.vue'
import TalentSettlementDetail from './TalentSettlementDetail.vue'
import TalentMediaSamples from './TalentMediaSamples.vue'
import { talentGradeLabel } from '@/utils/talentGrade'
import { interpretationRatingLabel, interpretationRatingHint } from '@/utils/talentPerformance'
import { contactAvailabilityLabel } from '@/utils/talentContactAvailability'

defineEmits(['reload-projects'])
const props = defineProps({
  inDialog: Boolean,
  projectsLoading: Boolean,
  projectsError: String,
  detail: { type: Object, default: () => ({}) },
  section: { type: String, default: 'all' },
  projects: { type: Array, default: () => [] },
  showPerformance: { type: Boolean, default: true },
  showAnnotationWillingness: { type: Boolean, default: true },
})

const contactRestricted = computed(() => props.detail.contactRestricted === true)
const displayLanguageSkills = computed(() => normalizeForeignLanguagePriorities(props.detail.languageSkills || []))

const shows = (section) => props.section === 'all' || props.section === section
const resumeTab=ref('zh'),foreignResumeLocale=ref('ar')
watch(()=>props.detail.id,()=>{resumeTab.value='zh'})
const resumeProfile=computed(()=>resumeProfileForm(props.detail.resumeProfile,props.detail))
const educationRows=computed(()=>educationFormRows(props.detail.educationExperiences||[],props.detail.resumeProfile?.educationPeriods))
const localizedVersion=computed(()=>({...emptyResumeVersion(),...(resumeProfile.value.versions[resumeTab.value==='en'?'en':foreignResumeLocale.value]||{})}))
const resumeWorkGroups=[{key:'annotation',label:'标注类经验'},{key:'interpretation',label:'口译经验'},{key:'translation',label:'笔译经验'},{key:'other',label:'其他经验'}]
const formatOperationTime = value => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}年${pad(date.getMonth()+1)}月${pad(date.getDate())}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
const show = (value) => value === null || value === undefined || value === ''
  ? '-'
  : Array.isArray(value) ? (value.join('、') || '-') : value
const join = (...values) => values.filter(Boolean).join(' · ') || '-'
const performanceLevelLabel = value => ({ high: '高', medium: '中', low: '低' }[value] || '')
const scoreAndEvaluation = (score, evaluation) => [score == null ? '' : `${score}分`, String(evaluation || '').trim()].filter(Boolean).join(' · ') || '-'
const levelAndNote = (level, note) => [performanceLevelLabel(level), String(note || '').trim()].filter(Boolean).join(' · ') || '-'
const statusLabel = talentStatusLabel
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

<style scoped>
.talent-detail-content.is-dialog-content{max-height:none;overflow:visible}.talent-detail-content :deep(section>h4),.talent-detail-content :deep(.el-collapse-item__content>h5){display:none}
</style>

<style scoped>.resume-tabs-summary :deep(>.el-tabs__header){display:none}</style>
