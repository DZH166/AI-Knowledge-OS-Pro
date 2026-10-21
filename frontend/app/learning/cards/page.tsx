"use client";

import { useEffect, useState } from "react";

import { EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api, statusLabel } from "@/services/api";
import type { LearningCard, QuizQuestion } from "@/types/api";

export default function LearningCardsPage() {
  const [cards, setCards] = useState<LearningCard[]>([]);
  const [quizzes, setQuizzes] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [cardData, quizData] = await Promise.all([api.learningCards(), api.quizzes()]);
      setCards(cardData);
      setQuizzes(quizData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }
  useEffect(() => { load(); }, []);

  async function review(id: number, mastery_status: string) {
    await api.reviewLearningCard(id, mastery_status);
    await load();
  }

  async function answerQuiz(id: number) {
    const result = await api.answerQuiz(id, answers[id] || "");
    setFeedback((old) => ({ ...old, [id]: result.correct ? "回答正确" : `需要复习：${result.explanation}` }));
    await load();
  }

  return (
    <div className="page">
      <PageHeader eyebrow="学习成长" title="学习卡片与练习" description="用会了、模糊、不会来记录复习结果；答错的练习会把知识点放回待复习。" />
      {error && <ErrorState message={error} onRetry={load} />}
      <section className="grid cols-2">
        <div className="panel">
          <h2>学习卡片</h2>
          <div className="list">
            {cards.length ? cards.map((card) => (
              <article className="list-item" key={card.id}>
                <div className="row between"><strong>{card.front}</strong><StatusBadge status={card.mastery_status} label={statusLabel(card.mastery_status)} /></div>
                <p>{card.back}</p>
                <p className="muted">复习 {card.review_count} 次</p>
                <div className="row wrap">
                  <button className="button secondary small" onClick={() => review(card.id, "know")} type="button">会了</button>
                  <button className="button secondary small" onClick={() => review(card.id, "unclear")} type="button">模糊</button>
                  <button className="button secondary small" onClick={() => review(card.id, "unknown")} type="button">不会</button>
                </div>
              </article>
            )) : <EmptyState title="暂无卡片" description="确认版本学习包后会生成卡片。" />}
          </div>
        </div>
        <div className="panel">
          <h2>练习中心</h2>
          <div className="list">
            {quizzes.length ? quizzes.map((quiz) => (
              <article className="list-item" key={quiz.id}>
                <strong>{quiz.question}</strong>
                <select className="select" onChange={(event) => setAnswers((old) => ({ ...old, [quiz.id]: event.target.value }))} value={answers[quiz.id] || ""}>
                  <option value="">选择答案</option>
                  {quiz.options.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
                <button className="button secondary small" onClick={() => answerQuiz(quiz.id)} type="button">提交</button>
                {feedback[quiz.id] && <span className="pill gray">{feedback[quiz.id]}</span>}
              </article>
            )) : <EmptyState title="暂无练习" description="学习包确认后会生成练习题。" />}
          </div>
        </div>
      </section>
    </div>
  );
}
