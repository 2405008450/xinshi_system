# 新时系统前端

基于 Vue 3 + Element Plus 的前端管理系统

## 功能特性

- ✅ 用户管理（CRUD）
- ✅ 角色管理（CRUD）
- ✅ 项目管理（CRUD）
- ✅ 用户角色关联管理
- ✅ 项目文件管理（CRUD）
- ✅ 登录功能

## 技术栈

- Vue 3
- Element Plus
- Vue Router
- Axios
- Vite

## 安装依赖

```powershell
Set-Location -LiteralPath 'E:\xinshi_system\frontend'
npm.cmd ci
```

## 开发

在本 PC 已登录桌面会话中，先按 [本机启动说明](../docs/infra.md#本机启动与验收) 启动后端，然后执行：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\deploy\start_local.ps1 -Service Frontend
```

也可双击 `frontend/start_frontend.bat`。访问 http://localhost:3000；Vite 默认绑定 `127.0.0.1:3000`，端口被占用时直接报错。开发代理 `/api` 默认转发到 `http://127.0.0.1:8000`，支持 WebSocket；需要覆盖时在前端本地配置中设置 `VITE_API_PROXY_TARGET`。

## 构建

```powershell
npm.cmd run build
```

若 Nginx 正在服务 `frontend/dist`，使用 `tools/publish-lan-frontend.ps1` 两阶段发布，避免直接覆盖正在服务的目录。

## 项目结构

```
frontend/
├── src/
│   ├── api/          # API 接口
│   ├── views/        # 页面组件
│   ├── layout/       # 布局组件
│   ├── router/       # 路由配置
│   ├── App.vue       # 根组件
│   └── main.js       # 入口文件
├── index.html
├── package.json
└── vite.config.js
```

## 注意事项

1. 确保后端服务运行在 http://127.0.0.1:8000
2. 登录功能目前是简化版本，实际项目中需要实现完整的认证流程
3. 部分接口可能需要根据实际后端响应调整


路由结构：
/ (Layout)
├── /users - 用户管理
├── /roles - 角色管理
├── /user-roles - 用户角色关联
├── /project-management (项目管理)
│   ├── /translation - 笔译项目管理
│   ├── /interpretation - 口译项目管理
│   ├── /annotation - 标注项目管理
│   ├── /recruitment - 招聘项目管理
│   └── /other - 其他项目管理
├── /project-details - 项目详情
├── /project-files - 项目文件
├── /resource-management (资源管理)
│   └── /translators - 译员信息
└── /client-management (客户管理)
    ├── /clients - 客户信息
    ├── /subsidiary-clients - 子公司客户信息
    ├── /client-contacts - 客户联系人及回访
    └── /consultations - 咨询基本情况
