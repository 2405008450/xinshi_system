<template>
  <div class="resume-experience-grid" :class="{'is-rtl':rtl}">
    <div class="experience-grid-actions"><span>{{ modelValue.length }} {{ bilingual?'条 / entries':'条经历' }}</span><el-button v-if="!readonly" type="primary" plain size="small" @click="add">{{ bilingual?'添加经历 / Add experience':'添加经历' }}</el-button></div>
    <div class="experience-grid-scroll">
      <table class="experience-grid" @keydown="handleTableArrowNavigation">
        <colgroup><col class="experience-index"/><col class="experience-period"/><col/><col class="experience-position"/><col v-if="education" class="experience-degree"/><col v-if="!readonly" class="experience-action"/></colgroup>
        <thead><tr><th>#</th><th>{{ label('起止年月日','Period') }}</th><th>{{ education?label('学校','School'):label('工作单位','Organization') }}</th><th>{{ education?label('专业','Major'):label('职位','Position') }}</th><th v-if="education">{{ label('学历','Education') }}</th><th v-if="!readonly">{{ label('操作','Actions') }}</th></tr></thead>
        <tbody v-for="(row,index) in modelValue" :key="row._key || row.id" data-dialog-field-search-group>
          <tr>
            <td rowspan="2" class="experience-index"><span data-dialog-field-search-group-title>{{ groupTitle }} {{ index+1 }}</span></td>
            <td><span v-if="readonly">{{ row.period || '-' }}</span><el-form-item v-else :label="label('起止年月日','Period')" :prop="path(index,'period')" class="experience-cell-field"><GridInput v-model="row.period" maxlength="100" placeholder="2022-06 – 2024-03" class="experience-period-input" /></el-form-item></td>
            <td><span v-if="readonly">{{ row[keys.organization] || '-' }}</span><el-form-item v-else :label="education?label('学校','School'):label('工作单位','Organization')" :prop="path(index,keys.organization)" class="experience-cell-field"><GridInput v-model="row[keys.organization]" maxlength="255" /></el-form-item></td>
            <td><span v-if="readonly">{{ row[keys.position] || '-' }}</span><el-form-item v-else :label="education?label('专业','Major'):label('职位','Position')" :prop="path(index,keys.position)" class="experience-cell-field"><GridInput v-model="row[keys.position]" maxlength="255" /></el-form-item></td>
            <td v-if="education"><span v-if="readonly">{{ degreeOptions.find(item=>item.value===row[keys.degree])?.label || row[keys.degree] || '-' }}</span><el-form-item v-else :label="label('学历','Education')" :prop="path(index,keys.degree)" :rules="canonicalEducation?[{required:true,message:'请选择学历',trigger:'change'}]:[]" class="experience-cell-field"><el-select v-model="row[keys.degree]" clearable placeholder="" no-data-text="—" no-match-text="—" :popper-class="rtl?'resume-options-rtl':''"><el-option v-for="item in degreeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></td>
            <td v-if="!readonly" rowspan="2" class="experience-row-actions">
              <el-button type="danger" link size="small" @click="remove(index)">{{ bilingual?'移除 / Remove':'移除' }}</el-button>
              <el-popover v-if="canonicalEducation" trigger="click" placement="left" :width="380" title="学历补充资料">
                <template #reference><el-button link type="primary" size="small">更多</el-button></template>
                <div class="education-extra-fields">
                  <el-form-item label="毕业年份"><el-input-number v-model="row.graduationYear" :min="1900" :max="2200" :precision="0" /></el-form-item>
                  <el-form-item v-for="field in extraFields" :key="field.key" :label="field.label"><GridInput v-model="row[field.key]" /></el-form-item>
                </div>
              </el-popover>
            </td>
          </tr>
          <tr><td :colspan="education?4:3" class="experience-description"><strong>{{ education?label('学习说明','Study details'):label('任职说明','Responsibilities') }}</strong><div v-if="readonly" class="experience-description-text">{{ row[keys.description] || '-' }}</div><el-form-item v-else :label="education?label('学习说明','Study details'):label('任职说明','Responsibilities')" :prop="path(index,keys.description)" class="experience-cell-field"><GridInput v-model="row[keys.description]" type="textarea" :autosize="{minRows:2,maxRows:8}" /></el-form-item></td></tr>
        </tbody>
        <tbody v-if="!modelValue.length"><tr><td :colspan="(education?5:4)+(!readonly?1:0)" class="experience-empty">{{ bilingual?'暂无经历 / No entries':'暂无经历，点击添加经历填写' }}</td></tr></tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import {ElInput as GridInput} from 'element-plus'
import 'element-plus/es/components/input/style/css'
import {educationDegreeOptions,newExperience,newEducation} from '@/utils/talentResumeProfile'
import {handleTableArrowNavigation} from '@/utils/tableArrowNavigation'
const props=defineProps({modelValue:{type:Array,default:()=>[]},propPrefix:String,education:Boolean,canonicalEducation:Boolean,readonly:Boolean,bilingual:Boolean,rtl:Boolean,groupTitle:{type:String,default:'经历'},degreeOptions:{type:Array,default:()=>educationDegreeOptions}})
const emit=defineEmits(['update:modelValue'])
const keys=computed(()=>props.canonicalEducation?{organization:'institution',position:'major',degree:'educationLevel',description:'remarks'}:{organization:'organization',position:'position',degree:'degree',description:'description'})
const extraFields=[{key:'institutionCategory',label:'院校分类'},{key:'majorCategory',label:'专业分类'},{key:'minorMajor',label:'辅修专业'},{key:'degreeName',label:'学位名称'}]
const label=(zh,en)=>props.bilingual?`${zh} / ${en}`:zh
const path=(index,key)=>props.propPrefix?`${props.propPrefix}.${index}.${key}`:undefined
function add(){emit('update:modelValue',[...props.modelValue,props.canonicalEducation?newEducation():newExperience()])}
function remove(index){emit('update:modelValue',props.modelValue.filter((_,position)=>position!==index))}
</script>
<style scoped>
.experience-grid-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0}.experience-grid-scroll{overflow-x:auto;border:1px solid var(--el-border-color);border-radius:6px}
.experience-grid{border-collapse:collapse;table-layout:fixed;width:100%;min-width:660px}.experience-grid th,.experience-grid td{border:1px solid var(--el-border-color-lighter);padding:5px;vertical-align:top;overflow-wrap:anywhere}.experience-grid th{background:var(--el-fill-color-light);font-size:13px;text-align:left}.experience-grid td{background:#fff}
.experience-index{width:48px;text-align:center;font-size:12px}.experience-period{width:180px}.experience-position{width:160px}.experience-degree{width:160px}.experience-action{width:65px}.experience-row-actions .el-button{margin:4px 0}.experience-description strong{font-size:12px;color:var(--el-text-color-secondary)}.experience-description-text{white-space:pre-wrap;line-height:1.7}.experience-empty{padding:20px!important;color:var(--el-text-color-secondary)}
.experience-grid :deep(.el-form-item){margin-bottom:0}.experience-grid :deep(.experience-cell-field>.el-form-item__label){position:absolute;width:1px;height:1px;clip-path:inset(50%);overflow:hidden}.experience-grid :deep(.el-form-item.is-error){padding-bottom:18px}.experience-grid :deep(.el-input__wrapper),.experience-grid :deep(.el-textarea__inner){box-shadow:none;background:#fff;padding:5px}.experience-grid :deep(.el-input__wrapper.is-focus),.experience-grid :deep(.el-textarea__inner:focus){box-shadow:0 0 0 2px var(--el-color-primary) inset}.experience-grid :deep(.el-select){width:100%}.education-extra-fields{max-height:400px;overflow-y:auto}
.is-rtl :deep(.el-input__inner),.is-rtl :deep(.el-textarea__inner){direction:rtl;text-align:right}.is-rtl :deep(.experience-period-input .el-input__inner){direction:ltr;text-align:left}
</style>
