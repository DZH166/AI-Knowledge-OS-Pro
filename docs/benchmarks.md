# Benchmarks

## 1. 文本切片（Chunker）组件基准

脚本：[scripts/benchmark_chunking.py](../scripts/benchmark_chunking.py)
原始结果：[benchmarks_chunking.json](benchmarks_chunking.json)

环境：Windows，Python 3.12.9，单进程；合成中英混合文档，每篇约 2 KB，固定 `CHUNK_SIZE=1200` / `CHUNK_OVERLAP=180`。

| 文档数 | 产出 chunks | 耗时 | 文档/秒 | chunks/秒 | tracemalloc 峰值 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 3,000 | 1.01 s | 992.9 | 2,978.6 | 0.1 MB |
| 10,000 | 30,000 | 37.60 s | 266.0 | 797.9 | 0.0 MB |

**这不是端到端吞吐。** 它只测 `Chunker.split()` 的 CPU/内存，不包含 PDF 解析、embedding、SQLite 写入、Qdrant upsert 或检索。`tracemalloc` 也不统计 SQLAlchemy/Qdrant 的 C 扩展内存。

## 2. 怎么读这组数字

- 1,000 篇约 1 秒，说明切片本身不是瓶颈。
- 10,000 篇单进程约 38 秒；真实摄取还要加上解析、embedding 网络调用和向量写入，时间会明显更长。
- 10,000 篇的“文档/秒”比 1,000 篇低，可能是单次运行中的 CPU 调度/缓存差异，不应据此推断算法复杂度；需要多次重复取中位数才算严格基准。
- 当前测试机器是本地 Windows，不是 CI 基准机；数字只用于发现量级问题，不作为 SLA。

## 3. 下一步：端到端基准

要做“1k/10k 文档能不能用”的结论，需要补：

1. 生成 1k/10k 个真实结构的 PDF/Markdown；
2. 启动 Redis/Qdrant/Worker；
3. 记录摄取总耗时、失败率、队列深度、embedding 调用数；
4. 对 50–100 个查询记录检索 p50/p95、Recall@10、引用有效率；
5. 记录 SQLite/Qdrant 磁盘增长与进程 RSS。

在此之前，不要对外说“支持 10k 文档”；只能说“切片组件在 10k 合成文档上单进程约 38 秒”。
