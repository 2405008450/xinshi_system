# 标准化迭代发布手册
--开发环境导出数据库
New-Item -ItemType Directory -Force -Path .\backups | Out-Null
$env:PGPASSWORD="XinShi@2026#PgS3cure!"
pg_dump -h localhost -p 5432 -U postgres -d xinshi_system -f ".\backups\xinshi_system_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').sql"


--删除创建和导入数据库
docker exec -it xinshi_postgres psql -U postgres -c "DROP DATABASE IF EXISTS xinshi_system WITH (FORCE);"
docker exec -it xinshi_postgres psql -U postgres -c "CREATE DATABASE xinshi_system;"
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < /home/ubuntu/xinshi_system/backups/xinshi_system_2026-03-16_192847.sql


适用范围：
- 后端代码更新
- 前端代码更新
- PostgreSQL 数据库结构或数据变更
- Docker + Nginx 部署场景

当前项目默认信息：
- 项目目录：`/home/ubuntu/xinshi_system`
- 前端目录：`/home/ubuntu/xinshi_system/frontend`
- 前端静态目录：`/var/www/html/`
- 数据库容器：`xinshi_postgres`
- 后端容器：`xinshi_backend`
- 数据库名：`xinshi_system`
- 数据库用户：`postgres`

说明：
- 本文档默认服务器使用 `docker compose`。如果你的服务器只有旧版命令，请把文中的 `docker compose` 替换为 `docker-compose`。
- 涉及数据库更新时，必须先备份，再执行变更，再验证。

## 1. 发布前检查清单

每次发布前先确认以下事项：

- 已提交本次代码，避免本地遗漏文件。
- 已确认是否涉及数据库变更。
- 已准备本次数据库 SQL 脚本。
- 已确认服务器磁盘空间、Docker、PostgreSQL 正常。
- 已确认前端是否需要重新打包。
- 已确认是否需要停机窗口或避开业务高峰期。

建议把每次数据库变更都单独保存一份 SQL 文件，命名规范如下：

```text
data/migrations/YYYYMMDD_变更说明.sql
```

例如：

```text
data/migrations/20260316_add_project_chat_tables.sql
data/migrations/20260316_fix_translation_project_status.sql
```

每个 SQL 文件建议包含：
- 变更目的
- 影响表
- 执行顺序
- 回滚说明

## 2. 标准发布流程

### 2.1 只更新代码，不改数据库

适用于：
- 前端页面调整
- 后端接口逻辑调整
- 配置更新
- 不涉及表结构和历史数据修正

执行步骤：

```bash
# 1. 进入项目目录
cd /home/ubuntu/xinshi_system

# 2. 拉取最新代码
git pull

# 3. 重建并启动后端服务
docker compose up -d --build backend

# 4. 重新构建前端
cd /home/ubuntu/xinshi_system/frontend
npm install
npm run build

# 5. 覆盖 Nginx 静态文件
sudo rm -rf /var/www/html/*
sudo cp -r /home/ubuntu/xinshi_system/frontend/dist/* /var/www/html/

# 6. 检查 Nginx 配置并重启
sudo nginx -t
sudo systemctl restart nginx
```

发布后验证：

```bash
# 查看后端日志
docker compose logs -f backend

# 查看容器状态
docker compose ps
```

### 2.2 代码更新 + 数据库更新

适用于：
- 新增表、字段、索引
- 修改字段类型或约束
- 初始化新功能数据
- 修复线上脏数据

标准顺序：

1. 备份数据库
2. 拉取最新代码
3. 执行数据库变更 SQL
4. 重启后端
5. 重新构建前端
6. 业务验证

## 3. 数据库更新标准流程

### 3.1 先备份数据库

强烈建议每次数据库变更前先导出备份：

```bash
cd /home/ubuntu/xinshi_system
mkdir -p backups

docker exec xinshi_postgres pg_dump -U postgres -d xinshi_system > backups/xinshi_system_$(date +%F_%H%M%S).sql
```

如果需要压缩备份：

```bash
docker exec xinshi_postgres pg_dump -U postgres -d xinshi_system | gzip > backups/xinshi_system_$(date +%F_%H%M%S).sql.gz
```

### 3.2 上传或准备本次 SQL 脚本

如果 SQL 文件在本地，先上传到服务器，例如：

```bash
scp data/migrations/20260316_add_project_chat_tables.sql ubuntu@43.160.215.225:/home/ubuntu/xinshi_system/data/migrations/
```

### 3.3 执行数据库变更

方式一：直接在服务器执行 SQL 文件

```bash
cd /home/ubuntu/xinshi_system
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < data/migrations/20260316_add_project_chat_tables.sql
```

方式二：进入容器后手动执行

```bash
docker exec -it xinshi_postgres psql -U postgres -d xinshi_system
```

进入 `psql` 后可执行：

```sql
\dt
\d 表名
SELECT COUNT(*) FROM 表名;
```

### 3.4 执行完成后重启服务

```bash
cd /home/ubuntu/xinshi_system
docker compose up -d --build backend
```

如果前端也有更新，再执行：

```bash
cd /home/ubuntu/xinshi_system/frontend
npm install
npm run build
sudo rm -rf /var/www/html/*
sudo cp -r /home/ubuntu/xinshi_system/frontend/dist/* /var/www/html/
sudo systemctl restart nginx
```

## 4. 数据库全量导出与导入

### 4.1 导出数据库

服务器内导出：

```bash
docker exec xinshi_postgres pg_dump -U postgres -d xinshi_system > xinshi_system.sql
```

本地导出：

```bash
pg_dump -U postgres -d xinshi_system -f xinshi_system.sql
```

### 4.2 导入数据库

适用于整库恢复或首次覆盖导入：

```bash
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < xinshi_system.sql
```

### 4.3 清空并重建数据库后导入

适用于需要整库重置的场景。这个操作风险较高，只能在确认无误后执行。

```bash
docker exec -it xinshi_postgres psql -U postgres -c "DROP DATABASE IF EXISTS xinshi_system WITH (FORCE);"
docker exec -it xinshi_postgres psql -U postgres -c "CREATE DATABASE xinshi_system;"
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < xinshi_system.sql
```

## 5. 推荐的数据库变更规范

后续每次迭代涉及数据库时，建议统一执行以下规范：

### 5.1 一次迭代，一个 SQL 文件

不要把多次发布的数据库修改混在一个文件里。每次上线一个独立 SQL 文件，便于追溯、复盘和回滚。

### 5.2 SQL 文件建议结构

```sql
-- 版本：20260316_add_project_chat_tables
-- 目的：新增项目聊天相关表
-- 执行环境：production
-- 注意事项：执行前请先备份数据库

BEGIN;

-- 1. 建表 / 加字段 / 建索引

-- 2. 初始化数据

COMMIT;
```

如果是高风险修改，建议补充：

```sql
ROLLBACK;
```

说明：
- `ROLLBACK;` 不是回滚脚本本身，只是事务失败时的回退机制。
- 对于 `DROP COLUMN`、批量删除、不可逆数据修复，最好额外准备单独的回滚方案。

### 5.3 先结构，后数据，最后索引

推荐顺序：

1. 新增表/字段
2. 回填或修复历史数据
3. 增加索引和约束

这样失败时更容易定位问题，也更方便回滚。

### 5.4 禁止直接在线上手写零散 SQL

除紧急事故外，尽量不要临时敲一堆 SQL。应先整理成脚本，再执行，并保留在仓库中。

## 6. 回滚方案

如果发布后发现异常，优先按以下顺序处理：

### 6.1 代码回滚

```bash
cd /home/ubuntu/xinshi_system
git log --oneline -n 5
git checkout 指定稳定版本
docker compose up -d --build backend
```

前端同步回滚后重新打包：

```bash
cd /home/ubuntu/xinshi_system/frontend
npm install
npm run build
sudo rm -rf /var/www/html/*
sudo cp -r dist/* /var/www/html/
sudo systemctl restart nginx
```

### 6.2 数据库回滚

如果只是少量可逆 SQL，可以执行预先准备的回滚脚本。

如果数据库变更不可逆，直接使用发布前备份恢复：

```bash
docker exec -it xinshi_postgres psql -U postgres -c "DROP DATABASE IF EXISTS xinshi_system WITH (FORCE);"
docker exec -it xinshi_postgres psql -U postgres -c "CREATE DATABASE xinshi_system;"
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < backups/你的备份文件.sql
```

## 7. 发布后验证清单

数据库和代码发布完成后，至少检查以下内容：

- 首页是否可正常打开
- 登录是否正常
- 本次改动相关页面是否正常
- 本次改动相关接口是否返回正常
- 后端日志是否存在报错
- 数据库连接是否正常
- 新增字段/表是否已生效
- 历史数据修复是否符合预期

常用检查命令：

```bash
# 查看容器状态
docker compose ps

# 查看后端日志
docker compose logs --tail=200 backend

# 实时日志
docker compose logs -f backend

# 查看数据库容器日志
docker compose logs --tail=200 postgres

# 查看 Nginx 状态
sudo systemctl status nginx
```

## 8. 常用命令速查

### 8.1 Git

```bash
git status
git branch
git pull
git add .
git commit -m "feat: xxx"
git push
git log --oneline -n 10
```

### 8.2 Docker

```bash
docker compose ps
docker compose up -d
docker compose up -d --build
docker compose up -d --build backend
docker compose restart backend
docker compose restart postgres
docker compose stop
docker compose down
docker compose logs -f backend
docker compose logs -f postgres
docker compose logs --tail=200 backend
docker exec -it xinshi_postgres sh
docker exec -it xinshi_postgres psql -U postgres -d xinshi_system
```

### 8.3 PostgreSQL

```bash
# 导出
docker exec xinshi_postgres pg_dump -U postgres -d xinshi_system > xinshi_system.sql

# 导入
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < xinshi_system.sql

# 执行 SQL 文件
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < data/migrations/xxx.sql

# 进入 psql
docker exec -it xinshi_postgres psql -U postgres -d xinshi_system
```

`psql` 内常用命令：

```sql
\l
\c xinshi_system
\dt
\d 表名
\q
SELECT NOW();
SELECT COUNT(*) FROM 表名;
```

### 8.4 前端

```bash
cd /home/ubuntu/xinshi_system/frontend
npm install
npm run build
```

### 8.5 Nginx

```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl status nginx
sudo cp -r /home/ubuntu/xinshi_system/frontend/dist/* /var/www/html/
```

## 9. 建议你后续固定执行的发版模板

以后每次迭代，建议按下面这套模板执行。

### 9.1 无数据库变更

```bash
cd /home/ubuntu/xinshi_system
git pull
docker compose up -d --build backend

cd /home/ubuntu/xinshi_system/frontend
npm install
npm run build
sudo rm -rf /var/www/html/*
sudo cp -r dist/* /var/www/html/
sudo nginx -t
sudo systemctl restart nginx
```

### 9.2 有数据库变更

```bash
cd /home/ubuntu/xinshi_system
mkdir -p backups
docker exec xinshi_postgres pg_dump -U postgres -d xinshi_system > backups/xinshi_system_$(date +%F_%H%M%S).sql

git pull
docker exec -i xinshi_postgres psql -U postgres -d xinshi_system < data/migrations/本次变更.sql
docker compose up -d --build backend

cd /home/ubuntu/xinshi_system/frontend
npm install
npm run build
sudo rm -rf /var/www/html/*
sudo cp -r dist/* /var/www/html/
sudo nginx -t
sudo systemctl restart nginx
```

## 10. 最终建议

为了后续每次迭代更稳，建议固定执行这 4 条：

1. 每次数据库变更都单独落一个 SQL 文件
2. 每次执行 SQL 前先备份
3. 每次发布后检查日志和核心页面
4. 每次保留可回滚的代码版本和数据库备份
