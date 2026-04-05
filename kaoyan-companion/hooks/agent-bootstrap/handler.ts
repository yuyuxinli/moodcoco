export default async function handler(event: any) {
  if (event.type !== "agent" || event.action !== "bootstrap") return;

  const agentId = event.context.agentId;
  if (!agentId) return;

  const ENTRY_NAMES: Record<string, string> = {
    coco: "心情可可",
    kaoyan: "考研伴侣",
    selfhelp: "自助课",
    funtest: "趣味测试",
  };

  const entryName = ENTRY_NAMES[agentId] || agentId;

  event.context.bootstrapFiles.push({
    name: "ENTRY_POINT.md",
    content: [
      `## 当前入口：${entryName}`,
      ``,
      `用户从「${entryName}」入口进入。你只使用该入口对应的功能。`,
      `其他入口的功能对用户不可见，不要提及。`,
    ].join("\n"),
    path: `virtual://entry-${agentId}`,
    missing: false,
  });
}
