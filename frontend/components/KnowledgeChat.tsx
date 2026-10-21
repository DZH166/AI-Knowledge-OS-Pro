"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Bookmark,
  BookOpenCheck,
  Copy,
  GraduationCap,
  MessageSquare,
  RefreshCw,
  Send,
  Sparkles,
  Square,
  StickyNote
} from "lucide-react";

import { AnswerModeSelector } from "@/components/AnswerModeSelector";
import { CitationPanel } from "@/components/CitationPanel";
import { ButtonLoading, EmptyState, StatusBadge, Toast } from "@/components/ui";
import { api, statusLabel } from "@/services/api";
import type { AnswerMode, ChatMessage, ChatResponse, ChatSession, KnowledgeSpace } from "@/types/api";

export function KnowledgeChat({ spaces, defaultSpaceId, onAsked }: { spaces: KnowledgeSpace[]; defaultSpaceId?: number; onAsked?: () => void }) {
  const [spaceId, setSpaceId] = useState<number>(defaultSpaceId || spaces[0]?.id || 0);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [answerMode, setAnswerMode] = useState<AnswerMode>("normal");
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isSavingNote, setIsSavingNote] = useState(false);
  const ignoreCurrentResponse = useRef(false);
  const requestSeq = useRef(0);

  useEffect(() => {
    if (!spaceId) return;
    api.listChatSessions(spaceId).then(setSessions).catch(() => setSessions([]));
  }, [spaceId, result]);

  const currentSession = useMemo(() => sessions.find((session) => session.id === sessionId) || null, [sessionId, sessions]);
  const lastAssistantMessage = useMemo(() => {
    const messages = currentSession?.messages || [];
    return [...messages].reverse().find((message) => message.role === "assistant") || null;
  }, [currentSession]);
  const displayResult = result || responseFromMessage(lastAssistantMessage);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const session = await api.createChatSession({ space_id: spaceId, answer_mode: answerMode, title: question.slice(0, 60) || "新的知识问答" });
    setSessionId(session.id);
    return session.id;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spaceId || !question.trim()) return;
    setError("");
    setIsAsking(true);
    ignoreCurrentResponse.current = false;
    const requestId = requestSeq.current + 1;
    requestSeq.current = requestId;
    try {
      const sid = await ensureSession();
      const response = await api.askInSession(sid, { question: question.trim(), answer_mode: answerMode });
      if (ignoreCurrentResponse.current || requestSeq.current !== requestId) return;
      setResult(response);
      setQuestion("");
      await refreshSessions(sid);
      onAsked?.();
    } catch (exc) {
      if (!ignoreCurrentResponse.current && requestSeq.current === requestId) setError(exc instanceof Error ? exc.message : "问答失败");
    } finally {
      if (requestSeq.current === requestId) {
        setIsAsking(false);
        ignoreCurrentResponse.current = false;
      }
    }
  }

  async function refreshSessions(activeSessionId = sessionId) {
    if (!spaceId) return;
    const nextSessions = await api.listChatSessions(spaceId);
    setSessions(nextSessions);
    if (activeSessionId) setSessionId(activeSessionId);
  }

  function stopGenerating() {
    ignoreCurrentResponse.current = true;
    requestSeq.current += 1;
    setIsAsking(false);
    setToast("已停止在页面展示本次回答。后端请求如果已经发出，会自然结束。");
  }

  async function regenerateLastAnswer() {
    if (!lastAssistantMessage) return;
    setError("");
    setIsRegenerating(true);
    try {
      const response = await api.regenerateMessage(lastAssistantMessage.id);
      setResult(response);
      await refreshSessions(lastAssistantMessage.session_id);
      setToast("已重新生成回答。");
      onAsked?.();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "重新生成失败");
    } finally {
      setIsRegenerating(false);
    }
  }

  async function toggleFavorite() {
    if (!lastAssistantMessage) return;
    try {
      const response = await api.favoriteMessage(lastAssistantMessage.id);
      await refreshSessions(lastAssistantMessage.session_id);
      setToast(response.is_favorite ? "已收藏这条回答。" : "已取消收藏。");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "收藏失败");
    }
  }

  async function saveAnswerAsNote() {
    if (!displayResult) return;
    setIsSavingNote(true);
    try {
      await api.createLearningNote({
        title: `问答笔记：${currentSession?.title || "知识问答"}`,
        content: displayResult.answer,
        tags: ["问答沉淀", "AI 学习"],
        qa_log_id: displayResult.qa_log_id,
        version_slug: "v2-5-product-learning-experience"
      });
      setToast("已保存为学习笔记，可以在学习中心继续复盘。");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "保存学习笔记失败");
    } finally {
      setIsSavingNote(false);
    }
  }

  function askInterviewExpression() {
    if (!displayResult) return;
    setAnswerMode("interview");
    setQuestion("请把刚才这段回答改写成适合面试表达的版本，要求包含技术链路、项目价值和我负责的工作。");
  }

  function askCardPrompt() {
    if (!displayResult) return;
    setQuestion("请基于刚才的回答，帮我整理 3 张学习卡片：正面是问题，背面包含小白解释、项目用法和常见错误。");
  }

  return (
    <div className="split">
      <form className="panel stack" onSubmit={handleSubmit}>
        <div className="row">
          <Sparkles size={18} />
          <h2>知识问答</h2>
        </div>
        <div className="field">
          <label htmlFor="space">知识库</label>
          <select className="select" id="space" onChange={(event) => { setSpaceId(Number(event.target.value)); setSessionId(null); }} value={spaceId}>
            {spaces.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="session">会话</label>
          <select
            className="select"
            id="session"
            onChange={(event) => {
              setSessionId(event.target.value ? Number(event.target.value) : null);
              setResult(null);
            }}
            value={sessionId || ""}
          >
            <option value="">新会话</option>
            {sessions.map((session) => <option key={session.id} value={session.id}>{session.title}</option>)}
          </select>
        </div>
        <AnswerModeSelector onChange={setAnswerMode} value={answerMode} />
        <div className="field">
          <label htmlFor="question">问题</label>
          <textarea className="textarea" id="question" onChange={(event) => setQuestion(event.target.value)} placeholder="例如：这份资料里关于 RAG 的关键结论是什么？" value={question} />
        </div>
        <div className="row wrap">
          {["总结这份资料的核心观点", "用小白语言解释 RAG 流程", "把内容整理成面试表达"].map((item) => (
            <button className="button secondary small" key={item} onClick={() => setQuestion(item)} type="button">{item}</button>
          ))}
        </div>
        {error && <span className="pill rose">{error}</span>}
        <div className="row wrap">
          <button className="button" disabled={!spaceId || !question.trim() || isAsking} type="submit">
            {isAsking ? <ButtonLoading label="生成中" /> : <><Send size={17} />提问</>}
          </button>
          {isAsking && (
            <button className="button secondary" onClick={stopGenerating} type="button">
              <Square size={15} />停止生成
            </button>
          )}
        </div>
      </form>
      <div className="stack">
        {toast && <Toast message={toast} onClose={() => setToast("")} />}
        <section className="panel stack">
          <div className="row between">
            <div className="row"><MessageSquare size={18} /><h2>AI 回答</h2></div>
            {displayResult && (
              <div className="row wrap">
                <button className="button secondary small" onClick={() => navigator.clipboard.writeText(displayResult.answer).then(() => setToast("回答已复制。"))} type="button">
                  <Copy size={15} />复制
                </button>
                <button className="button secondary small" disabled={!lastAssistantMessage || isRegenerating} onClick={regenerateLastAnswer} type="button">
                  {isRegenerating ? <ButtonLoading label="重生成" /> : <><RefreshCw size={14} />重生成</>}
                </button>
              </div>
            )}
          </div>
          {displayResult ? (
            <>
              <div className="status-line">
                <StatusBadge status={displayResult.runtime_mode} />
                <StatusBadge status={displayResult.retrieval_status} />
                <span className="pill gray">置信度 {statusLabel(displayResult.answer_confidence)}</span>
                {displayResult.retrieval_score !== null && <span className="pill gray">最高相似度 {displayResult.retrieval_score}</span>}
                {lastAssistantMessage?.is_favorite && <span className="pill gold">已收藏</span>}
              </div>
              <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{displayResult.answer}</ReactMarkdown></div>
              <div className="row wrap">
                <button className="button secondary small" onClick={() => setQuestion("请基于刚才的回答重新组织成更适合复习的版本")} type="button">
                  <RefreshCw size={14} />继续追问
                </button>
                <button className="button secondary small" disabled={!lastAssistantMessage} onClick={toggleFavorite} type="button">
                  <Bookmark size={14} />{lastAssistantMessage?.is_favorite ? "取消收藏" : "收藏回答"}
                </button>
                <button className="button secondary small" disabled={isSavingNote} onClick={saveAnswerAsNote} type="button">
                  {isSavingNote ? <ButtonLoading label="保存中" /> : <><StickyNote size={14} />保存笔记</>}
                </button>
                <button className="button secondary small" onClick={askCardPrompt} type="button">
                  <BookOpenCheck size={14} />转学习卡片
                </button>
                <button className="button secondary small" onClick={askInterviewExpression} type="button">
                  <GraduationCap size={14} />面试表达
                </button>
              </div>
            </>
          ) : (
            <EmptyState title="等待提问" description="选择知识库和回答模式后，系统会检索相关片段并返回引用来源。" />
          )}
        </section>
        {displayResult && <CitationPanel citations={displayResult.citations} relatedChunks={displayResult.related_chunks} />}
        {currentSession && currentSession.messages.length > 0 && (
          <section className="panel stack">
            <div className="row">
              <Sparkles size={18} />
              <h2>本轮会话</h2>
            </div>
            <div className="chat-transcript">
              {currentSession.messages.slice(-8).map((message) => (
                <article className={`chat-message ${message.role === "assistant" ? "assistant" : "user"}`} key={message.id}>
                  <strong>{message.role === "assistant" ? "AI" : "我"}</strong>
                  <p>{message.content}</p>
                </article>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function responseFromMessage(message: ChatMessage | null): ChatResponse | null {
  if (!message || message.role !== "assistant") return null;
  return {
    answer: message.content,
    citations: message.citations || [],
    used_citation_ids: message.used_citation_ids || [],
    related_chunks: message.related_chunks || [],
    answer_confidence: message.answer_confidence || "unknown",
    retrieval_score: null,
    retrieval_status: message.retrieval_status || "unknown",
    runtime_mode: "real",
    qa_log_id: message.qa_log_id || 0
  };
}
