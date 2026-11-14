import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StorageHealthPanel } from "./StorageHealthPanel";

describe("StorageHealthPanel", () => {
  it("renders the integrity affordance before the first check finishes", () => {
    const markup = renderToStaticMarkup(createElement(StorageHealthPanel, { autoCheck: false }));

    expect(markup).toContain("存储完整性");
    expect(markup).toContain("核对 SQLite、上传文件与活动证据版本是否一致");
    expect(markup).toContain("重新检查");
    expect(markup).toContain("核对内容指纹");
  });
});
