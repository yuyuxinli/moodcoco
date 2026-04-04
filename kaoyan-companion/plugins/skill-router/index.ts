/**
 * Skill Router Plugin
 *
 * 三层隔离的 Layer 2 和 Layer 3：
 * - before_prompt_build: 从 system prompt 中过滤非授权 skills
 * - before_tool_call: 拦截对非授权 skill 文件的读取
 *
 * Layer 1 (Bootstrap Hook) 在 hooks/agent-bootstrap/handler.ts 中实现。
 */

// ============================================================
// 路由配置：每个入口可以访问哪些 skills
// 添加新 skill 时只需修改这里
// ============================================================
const SKILL_ROUTES: Record<string, string[]> = {
  coco: [
    // 心情可可：核心 AI 陪伴 skills
    "breathing-ground",
    "chat",
    "check-in",
    "decision-cooling",
    "diary",
    "farewell",
    "growth-story",
    "mbti-game",
    "mood-flow",
    "onboarding",
    "pattern-mirror",
    "personality-analysis",
    "relationship-guide",
    "weekly-reflection",
  ],
  kaoyan: [
    // 考研伴侣：考研备考相关 skills
    "kaoyan-tracker",
    "kaoyan-daily-plan",
    "kaoyan-weekly",
    "kaoyan-diagnosis",
    "kaoyan-crisis",
    "kaoyan-quiz",
  ],
  selfhelp: [
    // 自助课（growth 成长入口）：自助心理课程相关 skills
    "course-dialogue",
    "motivation-guide",
  ],
};

// 所有入口共享的 skills（如果有的话放这里）
const SHARED_SKILLS: string[] = [];

/**
 * 获取某个入口的完整 skill 白名单（专属 + 共享）
 */
function getAllowedSkills(agentId: string): string[] {
  const entrySkills = SKILL_ROUTES[agentId] || [];
  return [...entrySkills, ...SHARED_SKILLS];
}

/**
 * 从 agentId 未知时，尝试从 context 中推断
 */
function getAgentId(context: any): string | null {
  // 优先从 context.agentId 获取（Bootstrap Hook 设置的）
  if (context?.agentId) return context.agentId;

  // 从 bootstrap files 中查找 ENTRY_POINT.md
  const bootstrapFiles = context?.bootstrapFiles || [];
  for (const file of bootstrapFiles) {
    if (file.path && typeof file.path === "string") {
      const match = file.path.match(/^virtual:\/\/entry-(\w+)$/);
      if (match) return match[1];
    }
  }

  return null;
}

// ============================================================
// Layer 2: before_prompt_build — 过滤 system prompt 中的 skills
// ============================================================
export async function before_prompt_build(event: any) {
  const agentId = getAgentId(event.context);
  if (!agentId) return; // 无法确定入口，不做过滤

  const allowed = getAllowedSkills(agentId);
  if (allowed.length === 0 && SHARED_SKILLS.length === 0) return; // 无 skill 限制

  const prompt = event.prompt;
  if (!prompt || typeof prompt !== "string") return;

  // 匹配 <available_skills> ... </available_skills> 块
  const skillsBlockRegex =
    /<available_skills>([\s\S]*?)<\/available_skills>/g;
  const match = skillsBlockRegex.exec(prompt);
  if (!match) return;

  const originalBlock = match[0];
  const innerContent = match[1];

  // 解析每个 <skill> 块，保留白名单中的
  const skillRegex = /<skill\s+name="([^"]+)">([\s\S]*?)<\/skill>/g;
  let filteredSkills = "";
  let skillMatch;

  while ((skillMatch = skillRegex.exec(innerContent)) !== null) {
    const skillName = skillMatch[1];
    if (allowed.includes(skillName)) {
      filteredSkills += skillMatch[0] + "\n";
    }
  }

  // 替换原始 block
  const newBlock = `<available_skills>\n${filteredSkills}</available_skills>`;
  event.prompt = prompt.replace(originalBlock, newBlock);
}

// ============================================================
// Layer 3: before_tool_call — 拦截对非授权 skill 文件的读取
// ============================================================
export async function before_tool_call(event: any) {
  const agentId = getAgentId(event.context);
  if (!agentId) return; // 无法确定入口，不拦截

  const toolName = event.tool?.name;

  // 只拦截文件读取类工具
  const readTools = ["read", "Read", "read_file", "cat"];
  if (!readTools.includes(toolName)) return;

  const filePath = event.tool?.arguments?.file_path || event.tool?.arguments?.path || "";
  if (typeof filePath !== "string") return;

  // 检查是否在 skills/ 目录下
  const skillsPathMatch = filePath.match(/skills\/([^/]+)\//);
  if (!skillsPathMatch) return; // 不是 skill 文件，放行

  const targetSkill = skillsPathMatch[1];
  const allowed = getAllowedSkills(agentId);

  // 共享 skills 和当前入口的 skills 都放行
  if (allowed.includes(targetSkill)) return;

  // 拦截：返回错误信息
  event.blocked = true;
  event.blockReason = `该功能不属于当前入口。skill "${targetSkill}" 不在「${agentId}」入口的授权范围内。`;
}
