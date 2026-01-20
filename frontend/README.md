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

```bash
npm install
# 或
yarn install
# 或
pnpm install
```

## 开发

```bash
npm run dev
```

访问 http://localhost:3000

## 构建

```bash
npm run build
```

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