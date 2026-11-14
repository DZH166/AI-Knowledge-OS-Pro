# 真实 Provider 配置与验证

目标：把系统从“确定性 recording demo”切到真实模型，同时不把 API Key 写进仓库。

## 1. 你需要准备的信息

最少需要两组：

| 用途 | 必填 | 说明 |
| --- | --- | --- |
| Chat / Agent 模型 | 是 | OpenAI-compatible `/chat/completions` |
| Embedding 模型 | 是 | OpenAI-compatible `/embeddings` |
| OCR / Vision | 否 | 图片文字、截图分析才需要 |
| Transcription | 否 | 音频/视频转写才需要 |
| Reranker | 否 | 有真实 HTTP rerank 服务才启用 |

请按下面格式发给我（**不要发到公开 issue/PR/commit**）：

```text
LLM_BASE_URL=
LLM_MODEL=
LLM_API_KEY=<your-key>
LLM_INPUT_COST_MICROS_PER_MILLION_TOKENS=
LLM_OUTPUT_COST_MICROS_PER_MILLION_TOKENS=

EMBEDDING_BASE_URL=
EMBEDDING_MODEL=
EMBEDDING_DIMENSIONS=
EMBEDDING_API_KEY=<your-key>

# 可选
OCR_BASE_URL=
OCR_MODEL=
OCR_API_KEY=<your-key>
TRANSCRIPTION_BASE_URL=
TRANSCRIPTION_MODEL=
TRANSCRIPTION_API_KEY=<your-key>
RERANK_URL=
RERANK_MODEL=
RERANK_API_KEY=<your-key>
```

注意：

- `LLM_API_KEY` 与 `EMBEDDING_API_KEY` 可以是同一个 Key，也可以是两个供应商。
- 有些模型供应商只提供 Chat，不提供 Embedding；这时 Embedding 需要单独选一家。
- `EMBEDDING_DIMENSIONS` 必须和模型实际输出维度一致，否则 Qdrant collection 维度会不匹配。
- 成本字段填“每百万 token 的微美元”（1 美元 = 1,000,000 微美元）；不知道可以留空，系统会标记 `cost_measurement=unknown`。

## 2. 本地配置步骤

```powershell
Copy-Item .env.example .env
# 编辑 .env，填入上面的值
```

`.env` 已被 `.gitignore` 忽略；不要 `git add .env`。

关键项：

```dotenv
DEMO_MODE=false
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-chat-model
LLM_API_KEY=sk-...

EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=https://your-provider.example/v1
EMBEDDING_MODEL=your-embedding-model
EMBEDDING_DIMENSIONS=1024
EMBEDDING_API_KEY=sk-...

QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
```

## 3. 启动与验证

```powershell
# 基础设施
docker compose up -d redis qdrant

# 后端
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# 另一个终端：Worker
cd backend
python -m app.worker
```

验证顺序：

1. `GET http://127.0.0.1:8000/api/system/status`：看 `llm`、`embedding`、`qdrant`、`redis` 是否 ready。
2. `POST /api/system/test-llm`：发一条最小 message，确认模型可调用。
3. `POST /api/system/test-embedding`：确认维度和向量返回。
4. 上传一份小文档，确认任务 `completed`、索引 `active`。
5. 在工作台提交一个真实问题，确认回答带引用、引用能跳到 locator。

## 4. 跑 20 题真实评测

准备 `evaluation/real_provider/questions.jsonl`（不要提交 Key）：

```jsonl
{"id":"r1","question":"这份资料的核心结论是什么？","expected_source":"guide.md"}
{"id":"r2","question":"作者为什么选择 SQLite？","expected_source":"adr/0003-sqlite-local-first.md"}
```

记录字段：

| 字段 | 说明 |
| --- | --- |
| `question` | 真实问题 |
| `expected_source` | 期望命中的来源（可选） |
| `retrieval_hit` | 是否命中期望来源 |
| `citation_valid` | 引用是否能回放到 locator |
| `answer_correct` | 人工判定 0/1 |
| `latency_ms` | 端到端延迟 |
| `input_tokens` / `output_tokens` | 模型用量 |
| `cost_micros` | 按单价估算 |
| `failure_reason` | 检索/生成/引用/拒答 |

报告里分开写：

- Deterministic CI：60/60、citation 1.0（合成固定集，不调用付费 API）。
- Real provider：20 题通过 X/20、p50/p95、平均成本、3 个失败案例。

## 5. 安全边界

- 不要把 Key 写进 README、issue、PR、截图或录屏。
- 真实模式不静默降级；Provider 失败时系统应该明确报错。
- 公开 demo 必须加认证/限流/预算上限，否则模型接口会被滥用。
- 录屏前先清空聊天记录和上传的私人资料，或使用专门的 demo 知识空间。
