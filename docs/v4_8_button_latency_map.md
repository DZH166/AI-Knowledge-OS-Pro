# V4.8 Button Latency Map

This map is generated from static TSX scanning. It is a prioritization aid, not a substitute for browser timing.

- Total button interactions: 79
- High duplicate-click risk: 0
- Medium local-feedback risk: 24

## Priority Findings

No high-risk async button was detected by the static scan.

## Interaction Inventory

| File | Route | Button | Pending/Disabled | Success | Failure | API-like | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `frontend/app/code/page.tsx` | `/code` | button-1 | yes | no | no | no | low |
| `frontend/app/documents/[id]/page.tsx` | `/documents/[id]` | 重建索引 | no | no | no | no | medium |
| `frontend/app/documents/[id]/page.tsx` | `/documents/[id]` | setConfirmDelete(true)} type="button"> 删除 | no | no | no | no | medium |
| `frontend/app/documents/[id]/page.tsx` | `/documents/[id]` | 确认删除 | no | yes | no | no | medium |
| `frontend/app/documents/[id]/page.tsx` | `/documents/[id]` | setConfirmDelete(false)} type="button">取消 | no | yes | no | no | medium |
| `frontend/app/documents/page.tsx` | `/documents` | 批量重建索引 | yes | no | yes | no | low |
| `frontend/app/documents/page.tsx` | `/documents` | 批量标签 | yes | no | no | no | low |
| `frontend/app/documents/page.tsx` | `/documents` | setConfirmingDelete(true)} type="button"> 批量删除 | yes | no | no | no | low |
| `frontend/app/documents/page.tsx` | `/documents` | 确认删除 | no | no | no | no | medium |
| `frontend/app/documents/page.tsx` | `/documents` | setConfirmingDelete(false)} type="button">取消 | no | no | no | no | medium |
| `frontend/app/knowledge/page.tsx` | `/knowledge` | button-1 | yes | no | no | no | low |
| `frontend/app/learning/cards/page.tsx` | `/learning/cards` | review(card.id, "know")} type="button"> | yes | no | no | yes | low |
| `frontend/app/learning/cards/page.tsx` | `/learning/cards` | review(card.id, "unclear")} type="button"> | yes | no | no | yes | low |
| `frontend/app/learning/cards/page.tsx` | `/learning/cards` | review(card.id, "unknown")} type="button"> | yes | no | no | yes | low |
| `frontend/app/learning/cards/page.tsx` | `/learning/cards` | answerQuiz(quiz.id)} type="button"> | yes | no | no | yes | low |
| `frontend/app/learning/knowledge-points/[id]/page.tsx` | `/learning/knowledge-points/[id]` | updateStatus("learning")} type="button">学习中 | yes | no | no | no | low |
| `frontend/app/learning/knowledge-points/[id]/page.tsx` | `/learning/knowledge-points/[id]` | updateStatus("understood")} type="button">已理解 | yes | no | no | no | low |
| `frontend/app/learning/knowledge-points/[id]/page.tsx` | `/learning/knowledge-points/[id]` | updateStatus("review_needed")} type="button">待复习 | yes | no | no | yes | low |
| `frontend/app/learning/knowledge-points/[id]/page.tsx` | `/learning/knowledge-points/[id]` | updateStatus("mastered")} type="button"> | yes | no | no | no | low |
| `frontend/app/learning/notes/page.tsx` | `/learning/notes` | 保存笔记 | no | no | no | no | medium |
| `frontend/app/learning/page.tsx` | `/learning` | {drafting ? ( ) : ( <> Generate package )} | yes | yes | yes | yes | low |
| `frontend/app/learning/page.tsx` | `/learning` | setActive(item)} type="button"> | no | no | no | no | medium |
| `frontend/app/learning/page.tsx` | `/learning` | confirm(active.slug)} type="button"> | yes | no | no | yes | low |
| `frontend/app/learning/quizzes/page.tsx` | `/learning/quizzes` | answerQuiz(quiz.id)} type="button"> | yes | no | no | yes | low |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | enqueueOperation(operation)} type="button"> | yes | no | no | no | low |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | seekTo(timestamp)} type="button"> {frame?.ocr_te | no | no | no | no | medium |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | setSelectedChunkId(chunk.id)} type="button" > # | no | no | no | no | medium |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | createLearningArtifacts(["knowledge_point"])} ty | yes | no | no | no | low |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | createLearningArtifacts(["card"])} type="button" | yes | no | no | no | low |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | createLearningArtifacts(["quiz"])} type="button" | yes | no | no | no | low |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | createLearningArtifacts(["note"])} type="button" | yes | no | no | no | low |
| `frontend/app/media/sources/[id]/page.tsx` | `/media/sources/[id]` | createLearningArtifacts(["knowledge_point", "car | yes | no | no | no | low |
| `frontend/app/portfolio/interview/page.tsx` | `/portfolio/interview` | button-1 | yes | no | no | yes | low |
| `frontend/app/portfolio/interview/page.tsx` | `/portfolio/interview` | button-2 | yes | yes | yes | yes | low |
| `frontend/app/portfolio/page.tsx` | `/portfolio` | button-1 | yes | no | no | yes | low |
| `frontend/app/portfolio/page.tsx` | `/portfolio` | button-2 | yes | yes | yes | yes | low |
| `frontend/app/portfolio/project-review/page.tsx` | `/portfolio/project-review` | button-1 | yes | no | no | yes | low |
| `frontend/app/portfolio/project-review/page.tsx` | `/portfolio/project-review` | button-2 | yes | yes | yes | yes | low |
| `frontend/app/portfolio/resume/page.tsx` | `/portfolio/resume` | button-1 | yes | no | no | yes | low |
| `frontend/app/portfolio/resume/page.tsx` | `/portfolio/resume` | button-2 | yes | yes | yes | yes | low |
| `frontend/app/system/observability/page.tsx` | `/system/observability` | 刷新 | yes | no | no | yes | low |
| `frontend/app/system/page.tsx` | `/system` | button-1 | yes | yes | no | no | low |
| `frontend/app/system/page.tsx` | `/system` | button-2 | yes | yes | yes | yes | low |
| `frontend/app/tasks/page.tsx` | `/tasks` | load(true)} type="button"> | yes | yes | no | yes | low |
| `frontend/app/tasks/page.tsx` | `/tasks` | setSelectedJobId(job.id)} type="button"> Task #  | no | yes | no | no | medium |
| `frontend/app/tasks/page.tsx` | `/tasks` | retry(selectedJob)} type="button" > {pendingJobI | yes | no | no | yes | low |
| `frontend/app/tasks/page.tsx` | `/tasks` | cancel(selectedJob)} type="button" > {pendingJob | yes | no | no | yes | low |
| `frontend/app/upload/page.tsx` | `/upload` | {busy ? ( ) : ( <> Upload )} | yes | no | no | yes | low |
| `frontend/components/AnswerModeSelector.tsx` | `component` | onChange(mode.value)} type="button"> | no | no | no | no | medium |
| `frontend/components/AppShell.tsx` | `component` | setMobileOpen(true)} type="button"> 菜单 | no | no | no | no | medium |
| `frontend/components/AppShell.tsx` | `component` | setCollapsed((old) => ( ))} type="button"> | no | no | no | no | medium |
| `frontend/components/DocumentUploader.tsx` | `component` | setQueue([])} type="button"> 清空队列 | no | no | no | no | medium |
| `frontend/components/DocumentUploader.tsx` | `component` | retry(item)} type="button"> 重试 | yes | no | yes | yes | low |
| `frontend/components/DocumentUploader.tsx` | `component` | item.status !== "ready") // isUploading} onClick | yes | yes | no | yes | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | setQuestion(item)} type="button"> | yes | no | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | button-2 | yes | yes | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | 停止生成 | yes | yes | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | navigator.clipboard.writeText(displayResult.answ | yes | yes | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | button-5 | yes | yes | no | yes | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | setQuestion("请基于刚才的回答重新组织成更适合复习的版本")} type="butt | yes | no | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | {isFavoriting ? : <> } | yes | no | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | button-8 | yes | no | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | 转学习卡片 | yes | no | no | no | low |
| `frontend/components/KnowledgeChat.tsx` | `component` | 面试表达 | no | no | no | no | medium |
| `frontend/components/media/TranscriptTimeline.tsx` | `component` | onSeek(segment.start_ms)} type="button"> | no | no | no | no | medium |
| `frontend/components/media/TranscriptTimeline.tsx` | `component` | { onSelectChunk(chunk?.id // null); onSeek(segme | no | no | no | no | medium |
| `frontend/components/ui.tsx` | `component` | button-1 | yes | yes | no | yes | low |
| `frontend/components/ui.tsx` | `component` | 关闭提示 | no | yes | no | no | medium |
| `frontend/components/ui.tsx` | `component` | 关闭 | yes | no | no | no | low |
| `frontend/components/ui.tsx` | `component` | button-4 | yes | no | no | yes | low |
| `frontend/components/ui.tsx` | `component` | button-5 | yes | no | no | no | low |
| `frontend/components/ui.tsx` | `component` | button-6 | no | no | no | no | medium |
| `frontend/components/ui.tsx` | `component` | navigator.clipboard.writeText(value)} title="复制代 | no | no | no | no | medium |
| `frontend/components/ui.tsx` | `component` | 关闭抽屉 | no | no | no | no | medium |
| `frontend/components/ui.tsx` | `component` | onPageChange(page - 1)} type="button"> 上一页 | yes | no | no | no | low |
| `frontend/components/ui.tsx` | `component` | = pageCount} onClick= type="button"> 下一页 | yes | no | no | no | low |
| `frontend/components/ui.tsx` | `component` | button-11 | yes | no | yes | no | low |
| `frontend/components/ui.tsx` | `component` | onChange(tab.key)} role="tab" type="button"> | no | no | no | no | medium |
| `frontend/components/ui.tsx` | `component` | button-13 | no | yes | no | no | medium |
