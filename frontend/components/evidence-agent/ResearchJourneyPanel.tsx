import Link from "next/link";

import styles from "./EvidenceAgent.module.css";

export type JourneyReadiness =
  | { state: "checking" | "unknown" | "ready" | "recording" }
  | { state: "blocked"; missing: string[] };

export function ResearchJourneyPanel({
  activeSourceCount,
  disabled = false,
  enabled,
  onToggle,
  readiness,
  selectedSourceCount,
  spaceId,
  totalSourceCount = activeSourceCount
}: {
  activeSourceCount: number;
  disabled?: boolean;
  enabled: boolean;
  onToggle: () => void;
  readiness: JourneyReadiness;
  selectedSourceCount: number;
  spaceId: number;
  totalSourceCount?: number;
}) {
  const remaining = Math.max(0, 3 - activeSourceCount);
  const processing = Math.max(0, totalSourceCount - activeSourceCount);

  return (
    <section aria-labelledby="comparison-journey-title" className={styles.journeyPanel} data-enabled={enabled}>
      <div className={styles.journeyIntro}>
        <div>
          <p className={styles.stepLabel}>推荐的第一次研究</p>
          <h2 id="comparison-journey-title">用三份资料做一次可核对的对比</h2>
          <p>{readiness.state === "recording"
            ? "录制样例可练习查看引用；真实研究完成后才能提交错误反馈。"
            : "先确定资料和比较维度，再查看报告中的每条证据；发现错误可以直接反馈。"}</p>
        </div>
        <button aria-pressed={enabled} className={styles.secondaryAction} disabled={disabled} onClick={onToggle} type="button">
          {enabled ? "退出对比流程" : "开始三资料对比"}
        </button>
      </div>

      {enabled && (
        <ol aria-label="对比研究准备状态" className={styles.journeySteps}>
          <li>
            <strong>准备资料</strong>
            {spaceId === 0 ? (
              <span>先创建知识空间。<Link href="/knowledge">创建知识空间</Link></span>
            ) : remaining > 0 && readiness.state === "recording" ? (
              <span>请切换到含三份示例资料的研究空间；录制样例不能通过真实上传中心增加资料。</span>
            ) : remaining > 0 ? (
              <span>
                还差 {remaining} 份可用资料；{processing > 0 ? `${processing} 份尚无可用版本。` : "上传后需等待索引完成。"}
                {processing > 0 && <Link href="/tasks">检查处理任务</Link>}
                <Link href={`/upload?space_id=${spaceId}&scenario=compare`}>前往上传资料</Link>
              </span>
            ) : (
              <span>已有 {activeSourceCount} 份可用资料，可在下方固定本次要比较的三份。</span>
            )}
          </li>
          <li>
            <strong>固定比较范围</strong>
            <span>{selectedSourceCount >= 3
              ? `已选择 ${selectedSourceCount} 份可用资料。`
              : `已选择 ${selectedSourceCount} 份；请在下方至少选择三份，并填写比较维度。`}</span>
          </li>
          <li>
            <strong>检查运行条件</strong>
            {readiness.state === "blocked" ? (
              <span>{readiness.missing.map((item) => `${item}未就绪`).join("、")}。<Link href="/system/settings">查看配置说明</Link></span>
            ) : readiness.state === "ready" ? (
              <span>所需服务已配置；提交时后端还会再次检查。</span>
            ) : readiness.state === "recording" ? (
              <span>录制样例，不会调用真实模型；报告不能当作真实质量评测。</span>
            ) : readiness.state === "checking" ? (
              <span>正在读取服务状态，不会发送模型请求。</span>
            ) : (
              <span>暂时无法确认配置状态；提交时后端会再次检查。</span>
            )}
          </li>
        </ol>
      )}
    </section>
  );
}
