# 存储完整性与备份

溯知 Evidence OS 把「引用可回放」建立在三件东西上：数据库里的 revision/index 台账、磁盘上的原始文件、以及二者之间的哈希身份。本页说明当前版本如何自检、备份和恢复，以及哪些能力还没有被承诺。

## 能保证什么

- SQLite 以 WAL 模式运行，`synchronous=FULL` 并开启外键约束；每个 Source 最多一个 active revision / active index revision（数据库唯一索引）。`FULL` 会增加每次提交的 fsync 成本，这是单用户本地工作区为断电后提交持久性付出的代价。
- 每次上传先把字节写入磁盘、`fsync` 并核对实际大小，再写数据库；文件路径、大小和内容 SHA-256 保存在 `sources` / `documents` / `media_assets` 中。写入失败会删除残留文件并返回明确错误。
- `存储完整性` 会检查：
  - SQLite `integrity_check` 与 `foreign_key_check`；
  - 数据库引用的文件是否存在、声明大小是否一致；
  - 可选地对每个文件重新计算 SHA-256，与登记值比对；
  - `active_revision_id` / `active_index_revision_id` 是否指向真实、状态正确的版本；
  - 版本声明的片段数、向量数是否与数据库实际行数一致；
  - 上传目录中是否存在没有被任何记录引用的孤儿文件。
- 只读自检不会修改业务数据；它可以在证据资料库页面点击「存储完整性」，也可以从命令行执行。

## 自检

```powershell
# 默认检查：数据库、文件存在性、版本台账、孤儿文件
python scripts/check_storage_integrity.py

# 更严格：逐个文件核对 SHA-256（大资料库会明显变慢）
python scripts/check_storage_integrity.py --deep-hash

# 指定数据库与上传目录，并保存 JSON 报告
python scripts/check_storage_integrity.py `
  --database-url "sqlite:///backend/data/knowledge_os.db" `
  --upload-dir backend/storage/uploads `
  --output .controlled_browser_logs/storage-health.json
```

退出码 `0` 表示没有阻断性错误；`2` 表示存在缺失文件、版本错位或数据库完整性问题。提醒级问题（大小不一致、片段数漂移、孤儿文件）不会阻止启动，但应尽快处理。

HTTP 接口：`GET /api/system/storage-health?deep_hash=false&scan_orphans=true`。

## 备份

备份使用 SQLite 在线备份 API，因此即使工作区正在运行，也能得到一致的数据库快照。归档内包含：

```text
manifest.json          # 格式版本、创建时间、原上传根目录、逐文件大小与 SHA-256、数据库 integrity=ok
database/knowledge_os.db
uploads/<原始相对路径>
```

```powershell
python scripts/backup_storage.py `
  --output backups/evidence-20261107.zip `
  --label "before-upgrade"

# 只验证，不创建
python scripts/backup_storage.py --verify backups/evidence-20261107.zip
```

创建完成后脚本会立即重新打开归档、逐文件核对哈希并执行数据库 `integrity_check`；任一失败都会以非零退出码结束。归档已存在时拒绝覆盖。

## 恢复

```powershell
python scripts/restore_storage.py `
  --archive backups/evidence-20261107.zip `
  --database-url "sqlite:///backend/data/knowledge_os.db" `
  --upload-dir backend/storage/uploads `
  --force
```

恢复会先完整验证归档，再解压到临时目录并再次执行 `integrity_check`，最后替换目标。若目标上传目录与备份时的根目录不同，会把 `sources` / `documents` / `media_assets` / `visual_frames` 中的绝对路径重写到新根目录，避免恢复后所有文件都被误判为孤儿；缺少 `source_upload_dir` 的旧归档不会猜测旧路径，恢复后需手动检查来源路径。目标非空时必须显式传入 `--force`；旧数据库、`-wal`/`-shm` 和旧上传目录会以 `.before-restore-<时间戳>` 的同级副本保留，不会静默删除。恢复前应停止 API 与 Worker，避免 Windows 文件句柄占用或运行中的写入覆盖恢复结果。

## 明确没有承诺的部分

- 没有云端复制、跨机高可用、静态加密或对象存储版本化；备份归档本身也不加密，需自行保护。
- SQLite 适合单用户本地工作区；多实例并发写入不在当前保证范围内。
- 自检能发现“文件缺失/哈希不符/台账错位”，但不会在没有原始 embedding 的情况下重建向量，也不会自动修复内容冲突。
- `deep_hash` 只核对文件内容，不验证外部 Qdrant 的实际 point 内容；那属于 `scripts/reconcile_evidence_index.py` 的职责。
