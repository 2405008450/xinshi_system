import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { ElMessage, ElTable } from 'element-plus'
// ElMessage、ElMessageBox、ElNotification 通过 JavaScript 调用，按需组件插件
// 无法从模板中识别并自动引入样式，必须在应用入口显式加载。
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-notification.css'
import './styles/theme.css'
import './styles/common.css'
import TableActionButton from './components/common/TableActionButton.vue'
import AppForm from './components/common/AppForm.vue'
import DraggableFormDialog from './components/common/DraggableFormDialog.vue'
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
app.component('TableActionButton', TableActionButton)

app.use(router)
// 增强新增、编辑表单：提交校验失败时滚动并聚焦到第一个错误字段。
app.component('AppForm', AppForm)
// 所有业务弹窗统一通过该组件获得拖拽、视口边界和位置复位能力。
app.component('DraggableFormDialog', DraggableFormDialog)
app.mount('#app')
