import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import styles from "./EvidencePresentation.module.css";

const plugins = [remarkGfm];
const components: Components = {
  h1: ({ children }) => <h3>{children}</h3>,
  h2: ({ children }) => <h4>{children}</h4>,
  h3: ({ children }) => <h5>{children}</h5>,
  h4: ({ children }) => <h6>{children}</h6>,
  h5: ({ children }) => <h6>{children}</h6>,
  h6: ({ children }) => <h6>{children}</h6>,
  a: ({ href, children }) => href ? <a href={href}>{children}</a> : <span>{children}</span>,
  img: ({ src, alt }) => <span>图片：{alt || "未提供说明"}{typeof src === "string" && src && <> · <a href={src} rel="noreferrer">查看图片链接</a></>}</span>,
  table: ({ children }) => <div aria-label="研究正文表格" className={styles.scrollRegion} role="region" tabIndex={0}><table>{children}</table></div>,
  pre: ({ children }) => <pre aria-label="研究正文代码" className={styles.codeBlock} role="region" tabIndex={0}>{children}</pre>
};

export function ArtifactBody({ markdown }: { markdown: string }) {
  return <div className={styles.body} data-testid="artifact-body"><ReactMarkdown components={components} remarkPlugins={plugins} skipHtml>{markdown}</ReactMarkdown></div>;
}
