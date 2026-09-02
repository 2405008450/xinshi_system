import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus, { ElMessage, ElTable } from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/theme.css'
import './styles/common.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import TableActionButton from './components/common/TableActionButton.vue'
import AppForm from './components/common/AppForm.vue'
import { installChineseMessageGuard } from './utils/errorMessages'
import { installChineseValidationMessages } from './utils/validationLocale'

const app = createApp(App)

installChineseValidationMessages()
installChineseMessageGuard(ElMessage)

// 表格的 show-overflow-tooltip 默认挂载在缩放后的 .el-table 内部，
// fixed 定位会因此重复计算缩放比例。统一挂到 body，保持与视口同一坐标系。
ElTable.props.tooltipOptions = {
  type: Object,
  default: () => ({ appendTo: 'body' }),
}

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.component('TableActionButton', TableActionButton)

app.use(router)
app.use(ElementPlus, { locale: zhCn })
// 增强新增、编辑表单：提交校验失败时滚动并聚焦到第一个错误字段。
app.component('AppForm', AppForm)
app.mount('#app')
