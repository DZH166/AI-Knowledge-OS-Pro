# V5.8 反馈审阅验收

状态：本阶段本地功能验收通过（2026-09-06，北京时间）。不代表真实模型质量或公网生产环境已经验收。

基线 8876e949c0d0da9dddf005fc2c9a66e7c552922a；分支 codex/v5.8-reviewed-feedback。

## 已完成的范围

- 成果或结论级反馈：服务器固定任务目标、运行模式、策略身份、原文和证据版本/片段/定位/指纹；拒绝跨成果、非最终成果、无效或超限快照。
- 创建与审阅幂等、过时版本冲突、真实并发重复请求去重。接受、审阅记录和唯一评测样例同事务提交；写入失败整体回滚；驳回不产生样例。
- 人工参考答案与验收要求；tuning / holdout 用途隔离，真实/演示/录制模式隔离；只导出明确选择的已接受样例，前后端验证选择和内容指纹。
- 成果页入口、反馈审阅页、服务端持久列表与游标分页、刷新后追溯、失败保留输入及请求标识、导出不清空未完成审阅、键盘与窄屏操作。
- Alembic `0017_reviewed_feedback`。从已有研究数据升级、带样例重复 upgrade、降级和再次升级通过；降级会删除本版本新增反馈数据，文档明确要求先备份，不承诺无损降级。
- Windows Docker 安全启动兼容入口；编码检查排除两个精确的浏览器生成目录，同时新增 PowerShell 源码检查，没有放宽源码乱码规则。

## 实测结果

| 检查 | 结果 |
| --- | --- |
| 全后端 `python -m pytest backend/tests -q --basetemp=.pytest_tmp/v58-release-verified --junitxml=.pytest_tmp/v58-backend-junit.xml` | **733 passed, 1 skipped**，774.37 秒 |
| 前端 `npm run test:unit` | **33 files / 121 tests passed** |
| 前端 lint / typecheck / 生产 build | 通过；44 个页面路由，生成 38 个静态页面（含框架路由） |
| `npm audit --omit=dev --audit-level=high` | 0 个已报告漏洞，不保证未知漏洞不存在 |
| 固定 Agent 评测 | **60/60**；外部模型调用 0；全部验收检查通过 |
| Strict E2E `v58-final-a` | **47/47**，浏览器执行部分 2.1 分钟 |
| Strict E2E `v58-final-b` | **47/47**，浏览器执行部分 3.9 分钟 |
| 静态检查 | Ruff、compileall、编码、版本、文档/图片链接、页面入口、交互反馈、缓存及 CI 清单通过 |
| 旧版演示与回归 | demo seed/readiness、RAG 引用与拒答检查、67 项演示全回归检查通过 |
| Provider dry-run | 模型、向量、OCR、视觉描述、转写、重排均明确未配置；未调用付费接口 |
| 发布预检 | 密钥扫描 0 发现；禁止追踪文件 0；发布清单排除数据库、上传、缓存等内容 |

固定评测原始证据：[evaluation_report.json](evaluation_report.json)、[evaluation_acceptance.json](evaluation_acceptance.json)。这是既有固定场景的回归证据，不是新反馈样例已经自动评分。

唯一跳过项：当前 Windows 无权创建无特权符号链接（WinError 1314）。该项不计为通过；Windows 目录联接保护仍执行。

## 红绿与对抗性过程

创建反馈、接受审阅、导出三个业务切片均先通过真实 HTTP 接口得到失败，再实现并验证成功。另覆盖无效输入、跨目标结论、原资料退役后的定位保留、快照破坏、演示数据被重标为真实模式、四路并发提交/审阅、写入失败回滚、分页和用途隔离。

首次浏览器回归为 44 passed / 2 failed：一项实测发现审阅失败后丢失表单；另一项是测试在导航完成前读取 URL。随后一次为 46 passed / 1 failed：成功提示与加载提示同时存在，测试定位过宽。分别修复应用生命周期和测试定位/等待，未删掉失败断言或降低业务要求，最终连续两轮 47/47。

第一次全后端为 727 passed / 4 failed / 1 skipped：三个失败来自正文使用未获准的 `<pre>` 标签，一个来自报告仍在生成时的缺失文档链接。改用正常文本容器、完成原始报告，并新增两个编码扫描回归后，全量重新执行得到 733 passed / 1 skipped。

## Standards

独立规范审查发现两项实质问题：审阅/导出触发详情重载导致草稿丢失；Docker 健康探测继承远端连接配置，且旧 UI 进程可能使历史错误被误判为当前故障。均已修复。

最终只读复查确认：详情读取不再依赖 busy；表单失败时保留输入与请求标识；安全启动显式绑定本机 Linux 引擎管道，并按当前最新 backend 启动时间核对错误。后续编码检查和文本容器修订复查也通过。

结论：**0 项仍待修复的阻断发现**，没有需要单列的代码异味。运行验收由主任务完成。

## Spec

独立需求审查确认审阅重试生命周期问题已修复，没有新的明确规格缺陷。后端原子性、幂等性、快照完整性和用途/模式隔离符合本阶段范围；Docker 修复来自用户明确追加请求，不属于范围扩张。

结论：**0 项仍待修复的明确规格发现**。两轴分开报告，不将其等同于不存在任何潜在缺陷。

## 浏览器与环境边界

两轮使用新的 SQLite、Redis、Qdrant 和三个 RQ Worker；前后端监听本机地址。每轮都精确停止自己创建的进程与容器，并清理临时数据库及 sidecars，没有碰正式资料。测试命令：

```text
python scripts/run_demo_e2e.py --strict --run-token v58-final-a --frontend-port 0 --backend-port 0 --redis-port 0 --qdrant-port 0
python scripts/run_demo_e2e.py --strict --run-token v58-final-b --frontend-port 0 --backend-port 0 --redis-port 0 --qdrant-port 0
```

浏览器使用 Next.js 开发服务器，生产构建独立验证；部分旧界面/错误场景有定向网络桩，新反馈主线来自真实后台保存的 demo 任务。额外目视检查了反馈工作台的空态布局。

保留运行现象：一轮出现 Windows asyncio 连接关闭的 WinError 10054；另一轮出现开发服务器临时 webpack 路径生成错误，随后同轮 47 个断言全部通过。没有全局吞异常、跳过测试或声称日志零告警。尚未完成生产运行模式 E2E 或压力测试，不能把这些结果当作生产就绪保证。

Docker 4.89.0 安装成功，但内置 restart 在本机仍会遇到不可访问通信文件。安全入口已验证故障恢复、两次正常退出后冷启动以及前后 8 个容器/8 个数据卷清单一致；原快捷方式与临时端点均保留备份。详见 [Docker 启动兼容记录](docker_startup_recovery.md)。

## 交付边界

本阶段没有真实模型接入、自动执行/评分新反馈样例、自动修改知识库、自动启用策略或多用户鉴权。人工参考答案不等于客观真理；holdout 标签表示用途隔离，不对数据库管理员隐藏答案。

发布包由 `scripts/release.py --version V5.8` 生成，并由 `scripts/check_release.py --version V5.8` 检查清单、内容指纹和当前源代码一致性。包本身的 SHA-256 保存在外置 `.sha256` 文件中，避免自引用。独立分支提交不等于合并 main 或发布正式 GitHub Release。
