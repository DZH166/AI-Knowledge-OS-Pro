# V5.13 运营质量与存储保证：范围说明

日期：2026-11-07（Asia/Shanghai）。产品显示版本保持 V5.8 / 5.8.0；本阶段是工程与体验加固，不是新的模型能力声明。

## 目标

1. **全量质量审查**：在干净环境安装依赖，运行后端全量测试、前端 lint/typecheck/unit/build 与关键浏览器流程，记录真实失败并修复。
2. **界面与分区**：核心产品页保持克制、干净；开发者工具入口不再出现明显的中英混排和不可读的原生控件；移动端不溢出。
3. **存储保证**：数据库、上传文件与版本台账具备只读自检、可验证备份与可回滚恢复，并在证据资料库直接可见。
4. **RAG 质量**：保持既有的确定性检索合同；补强切分配置边界与追问检索上下文，不伪造同义词理解。
5. **AI 智能化**：Agent 的计划、追问与综合保持目标语言一致；RAG 追问检索继承上一轮问题，但回答、历史与引用仍只对应原始问题。

## 不在范围

- 真实模型的答案质量、延迟与费用声明；本阶段不调用付费 API。
- 多租户鉴权、云部署、对象存储与跨机高可用。
- 重写既有 60 案例评测或 V5.12 中文检索合同。
- 把演示数据、合成样例或一次测试通过包装成生产级质量结论。

## 交付物

- `backend/app/services/storage_integrity.py`、`storage_backup.py` 及 API/CLI。
- `backend/tests/test_storage_integrity.py`、`test_storage_backup.py`、`test_chunker_contract.py`、`test_conversational_retrieval.py`、`test_agent_model_language.py`、`test_config_cors_origins.py`、`test_video_tooling_encoding.py`。
- 证据资料库的存储完整性面板；摄取、任务、媒体、学习页面的中文一致性；移动端布局修正。
- `docs/storage_integrity.md` 与本阶段审计/验收记录。
