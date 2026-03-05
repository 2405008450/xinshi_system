# 构建阶段
FROM node:18 as build

WORKDIR /app

# 复制package文件
COPY frontend/package*.json frontend/

# 安装依赖
RUN cd frontend && npm install

# 复制源代码
COPY frontend/ frontend/

# 构建
RUN cd frontend && npm run build

# Nginx阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=build /app/frontend/dist /usr/share/nginx/html

# 复制nginx配置
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
