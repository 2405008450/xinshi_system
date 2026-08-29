# 共享云数据库的本地迁移

常驻 API 启动时不会执行建表、改表或数据回填。云端部署不提供迁移入口。

代码版本包含数据库结构变更时，只能在本地开发机对共享云库执行一次迁移：

```powershell
$env:APP_ENV = "development"
$env:LOCAL_SCHEMA_MIGRATIONS_ENABLED = "true"
.\.venv\Scripts\python.exe -m tools.run_runtime_migrations
Remove-Item Env:LOCAL_SCHEMA_MIGRATIONS_ENABLED
```

执行迁移前应备份数据库，并确保没有另一个迁移进程正在运行。迁移完成后，本地和云端 API 只需更新至同一代码版本并重启。

## 连接池配置

默认每个 API 进程保留 5 个连接，并允许最多 5 个临时溢出连接。总连接上限按下式估算：

```text
实例数 × 每实例 worker 数 × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

调整 `.env` 中的 `DB_POOL_SIZE` 和 `DB_MAX_OVERFLOW` 即可覆盖默认值。
