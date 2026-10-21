"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Workflow } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/services/api";
import type { QuizQuestion } from "@/types/api";

export default function QuizzesPage() {
  const [quizzes, setQuizzes] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setQuizzes(await api.quizzes());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载练习失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function answerQuiz(id: number) {
    const result = await api.answerQuiz(id, answers[id] || "");
    setFeedback((old) => ({ ...old, [id]: result.correct ? "回答正确" : `需要复习：${result.explanation}` }));
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="学习成长"
        title="练习中心"
        description="用选择题检查自己是否真的理解了项目里的 RAG、任务队列、多模态和工程质量门。"
        action={
          <Link className="button" href="/learning/cards">
            <Workflow size={17} />
            查看学习卡片
          </Link>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      <section className="panel">
        <div className="list">
          {quizzes.length === 0 ? (
            <EmptyState title="暂无练习" description="确认学习包或从来源生成学习资料后，练习题会出现在这里。" />
          ) : (
            quizzes.map((quiz) => (
              <article className="list-item" key={quiz.id}>
                <strong>{quiz.question}</strong>
                <select className="select" onChange={(event) => setAnswers((old) => ({ ...old, [quiz.id]: event.target.value }))} value={answers[quiz.id] || ""}>
                  <option value="">选择答案</option>
                  {quiz.options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
                <button className="button secondary small" onClick={() => answerQuiz(quiz.id)} type="button">提交答案</button>
                {feedback[quiz.id] && <span className="pill gray">{feedback[quiz.id]}</span>}
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
