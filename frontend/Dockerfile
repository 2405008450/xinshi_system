# 构建阶段
FROM node:18-alpine AS build

WORKDIR /app

# 先复制 package.json 利用缓存
COPY frontend/package.json frontend/package-lock.json* ./

# 在容器内安装依赖（确保Linux权限正确）
RUN npm install

# 复制前端源代码
COPY frontend/ .

# 构建
RUN npm run build

# Nginx阶段
FROM nginx:alpine

# 从构建阶段复制产物
COPY --from=build /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
