"use client";

import type { AnswerMode } from "@/types/api";

const modes: Array<{ value: AnswerMode; label: string }> = [
  { value: "normal", label: "常规回答" },
  { value: "beginner", label: "小白解释" },
  { value: "project", label: "项目视角" },
  { value: "interview", label: "面试表达" }
];

export function AnswerModeSelector({ value, onChange }: { value: AnswerMode; onChange: (value: AnswerMode) => void }) {
  return (
    <div className="mode-tabs" role="tablist" aria-label="回答模式">
      {modes.map((mode) => (
        <button className={value === mode.value ? "active" : ""} key={mode.value} onClick={() => onChange(mode.value)} type="button">
          {mode.label}
        </button>
      ))}
    </div>
  );
}
