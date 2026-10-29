<template>
  <div class="localized-resume" :class="{'resume-rtl':rtl}">
    <p class="resume-shared-note">简历资料按语言独立保存；人才编号、联系方式、状态、项目、评价与结算共用，可在中文页签维护。</p>
    <CollapsibleSections :reset-key="locale">
      <el-collapse-item v-for="section in sections" :key="section.key" :name="`localized-${section.key}`" :data-section-key="`localized-${section.key}`" :title="section.label">
        <div v-if="section.key==='basic'" class="form-section"><h3 class="sr-only">基本资料 / Personal details</h3>
          <el-row :gutter="16"><el-col v-for="field in fields" :key="field.key" :xs="24" :md="12"><el-form-item :label="field.label" :prop="`${propPrefix}.${field.key}`">
            <span v-if="readonly" class="localized-value" :dir="rtl?'rtl':'ltr'">{{display(field)}}</span>
            <el-select v-else-if="field.options" v-model="modelValue[field.key]" clearable placeholder="" no-data-text="—" no-match-text="—" :popper-class="rtl?'resume-options-rtl':''"><el-option v-for="item in dictionaries[field.options]" :key="item.value" :value="item.value" :label="item.label" /></el-select>
            <GridInput v-else v-model="modelValue[field.key]" :maxlength="field.max||255" :placeholder="field.key==='birthDate'?'YYYY-MM-DD':''" :class="{'date-content':field.key==='birthDate'}" />
          </el-form-item></el-col></el-row>
        </div>
        <div v-else-if="section.key==='skills'" class="form-section"><h3 class="sr-only">语言与技能 / Languages and skills</h3>
          <el-form-item label="语言 / Languages" :prop="`${propPrefix}.languages`"><span v-if="readonly" class="localized-value">{{modelValue.languages.map(code=>languageOptions.find(item=>item.value===code)?.label||code).join(' · ')||'—'}}</span><el-select v-else v-model="modelValue.languages" multiple filterable placeholder="" no-data-text="—" no-match-text="—"><el-option v-for="item in languageOptions" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item>
          <el-form-item v-for="field in textFields" :key="field.key" :label="field.label" :prop="`${propPrefix}.${field.key}`"><span v-if="readonly" class="localized-value">{{modelValue[field.key]||'—'}}</span><GridInput v-else v-model="modelValue[field.key]" type="textarea" :autosize="{minRows:2,maxRows:8}" maxlength="20000" /></el-form-item>
          <el-form-item label="常用CAT经验 / CAT tools" :prop="`${propPrefix}.catTools`"><span v-if="readonly">{{modelValue.catTools.join(' · ')||'—'}}</span><el-select v-else v-model="modelValue.catTools" multiple filterable allow-create default-first-option placeholder="" no-data-text="—" no-match-text="—"><el-option v-for="item in catToolOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        </div>
        <ResumeExperienceGrid v-else v-model="modelValue[section.key]" :prop-prefix="`${propPrefix}.${section.key}`" :education="section.key==='educations'" :degree-options="dictionaries.degree" :readonly="readonly" :rtl="rtl" bilingual :group-title="section.label" />
      </el-collapse-item>
    </CollapsibleSections>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import {ElInput as GridInput} from 'element-plus'
import CollapsibleSections from '@/components/common/CollapsibleSections.vue'
import ResumeExperienceGrid from './ResumeExperienceGrid.vue'
import {catToolOptions} from '@/utils/talentResumeProfile'
import {resumeLocaleOptions,resumeLanguageOptions,isResumeRtl} from '@/utils/talentResumeLocales'
const props=defineProps({modelValue:{type:Object,required:true},locale:{type:String,required:true},propPrefix:String,readonly:Boolean})
const dictionaries=computed(()=>resumeLocaleOptions(props.locale)),languageOptions=computed(()=>resumeLanguageOptions(props.locale)),rtl=computed(()=>isResumeRtl(props.locale))
const fields=[{key:'name',label:'姓名 / Name'},{key:'professionalTitle',label:'职业称谓 / Professional title'},{key:'gender',label:'性别 / Gender',options:'gender'},{key:'birthDate',label:'出生日期 / Date of birth',max:20},{key:'nationality',label:'国籍 / Nationality'},{key:'residence',label:'目前所在地 / Residence',max:500},{key:'nativePlace',label:'主要成长地 / Place of upbringing'},{key:'employmentStatus',label:'职业状态 / Employment',options:'employment'},{key:'highestEducation',label:'最高学历 / Education',options:'degree'},{key:'height',label:'身高 / Height'},{key:'eyesight',label:'视力 / Eyesight'}]
const textFields=[{key:'languageNotes',label:'语言说明 / Language proficiency'},{key:'certificates',label:'证书 / Certificates'},{key:'skills',label:'技能 / Skills'}]
const sections=[{key:'basic',label:'基本资料 / Personal details'},{key:'skills',label:'语言与技能 / Languages and skills'},{key:'educations',label:'教育经历 / Education'},{key:'internships',label:'实习经历 / Internships'},{key:'annotation',label:'标注经验 / Annotation'},{key:'interpretation',label:'口译经验 / Interpreting'},{key:'translation',label:'笔译经验 / Translation'},{key:'other',label:'其他经验 / Other experience'}]
const display=field=>field.options?dictionaries.value[field.options].find(item=>item.value===props.modelValue[field.key])?.label||'—':props.modelValue[field.key]||'—'
</script>
<style scoped>
.resume-shared-note{font-size:12px;color:var(--el-text-color-secondary)}.localized-value{white-space:pre-wrap;overflow-wrap:anywhere;min-height:28px;display:block}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.localized-resume :deep(.el-select){width:100%}.resume-rtl :deep(.el-input__inner),.resume-rtl :deep(.el-textarea__inner){direction:rtl;text-align:right}.resume-rtl :deep(.date-content .el-input__inner){direction:ltr;text-align:left}
</style>
<style>.resume-options-rtl .el-select-dropdown__item{direction:rtl;text-align:right}</style>
