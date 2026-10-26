# GEO 审计：obsidian-kglite

审计日期 2026-10-26 · 对象 https://github.com/KRPCT/obsidian-kglite · 方法：按 seo-geo 的 GEO 判据对仓库公开面（README、description、topics、目录结构）逐项评估；未使用 DataForSEO 或 SE Ranking，因此平台分数留空，只给结构性就绪度。

## 1. GEO 就绪分：80/100

| 判据 | 权重 | 得分 | 依据 |
| --- | --- | --- | --- |
| 可引用性 | 25% | 22 | 首段是可独立引用的答案块；「已验证的事实」表给出可复现数字；每条事实标了来源文件 |
| 结构可读性 | 20% | 18 | 中文 README 采用 H2 问题式标题、FAQ、对照表；英文版同步结构化 |
| 多模态 | 15% | 11 | 三张图（总体关系、封口往返、写回路径），都是 Mermaid 源 + Pele 渲染 SVG，可缩放、可点开看原图；仍无视频、截图与交互件 |
| 权威与品牌信号 | 20% | 13 | 组织署名、MIT 许可、最后验证日期、上游一手来源；仓库新、无外部提及 |
| 技术可达性 | 20% | 16 | GitHub 服务端渲染 README，`raw.githubusercontent.com` 与 API 可直接取；AI 爬虫策略由 github.com 宿主决定，仓库无权设置 |

未测量项：任何平台的真实引用率与排名。平台拆分见第 3 节，只写就绪度不写分数。

## 2. 内容做了什么

- README 默认语言改为中文（`README.md`），英文版移到 `README.en.md`，两边顶部互相链接并标注适用版本与最后验证日期。
- 首屏 60 字内给出一句定义加一个具体问题域（"哪些笔记没有任何语义链接"），不做品牌铺垫。
- 新增「已验证的事实」表：5 篇 fixture 的构建数字、真实 26 篇 vault 的 14 处词干冲突、内联材料漂移检查结果。这些是别处没有的原创数据点。
- 新增 FAQ，用中文提问原句作 H3（会改动 vault 吗、需要 Obsidian 开着吗、中文支持吗、数据发到哪），每题答案自足。
- 新增「中文术语与图模型对照」表，把用户口语（孤儿笔记、断链、双链、章节、段落块）映射到图对象与查询入口，既服务中文读者，也让 agent 的检索词有落点。
- 图改为图源驱动：`docs/diagrams/*.mmd` 与 skill `assets/*.mmd` 是可编辑源，SVG 由 Pele 1.10.0 渲染并一起提交；总体关系图展示双向读写，往返流水线图展示封口步骤，写回路径图展示三条机制的副作用。改图改源，不手改 SVG。
- `SKILL.md` 的 description 改为中英双语触发词，覆盖"知识图谱/双链/断链/孤儿笔记"等中文说法；正文加入同一张术语对照表。

## 3. 平台就绪度（未测量）

| 平台 | 就绪度判断 | 依据 |
| --- | --- | --- |
| Google AI Overviews / AI Mode | 中 | 依赖 github.com 的索引与页面质量；README 结构、日期、来源齐备，但仓库是新的，尚无外部引用 |
| ChatGPT Search | 中 | 需要第三方页面提及；当前只有仓库自身，属于冷启动 |
| Perplexity | 中 | README 段落可被整段摘取，事实表提供了可验证数字 |

结论只到"就绪度"一级：没有工具测量，不给任何平台打引用分。

## 4. AI 爬虫访问状态

仓库层面无法设置 `robots.txt`：`github.com` 的策略由 GitHub 控制，仓库只控制内容是否可被读取。逐项说明，不合并成一行：

| 能力 | 相关爬虫 | 与本仓库的关系 |
| --- | --- | --- |
| ChatGPT Search 可引用 | `OAI-SearchBot` | 由 github.com 的宿主策略决定，仓库无法单独允许或禁止 |
| OpenAI 训练 | `GPTBot` | 同上；与本仓库的可引用性无关 |
| Claude 搜索可引用 | `Claude-SearchBot` | 同上 |
| Anthropic 训练 | `ClaudeBot` | 同上 |
| Google 搜索与 AI 概览 | `Googlebot` | 同上；`Google-Extended` 不决定搜索收录 |
| Gemini / Vertex 训练与 grounding | `Google-Extended` | 同上，且与搜索可引用性无关 |
| Perplexity 检索 | `PerplexityBot` | 同上 |

能实际控制的两件事：内容放在 GitHub 上可被匿名读取（`raw.githubusercontent.com`、`api.github.com`），以及不把关键信息放进需要 JavaScript 才能出现的位置。README 两者都满足。

## 5. llms.txt 状态：故意不添加

Google 的 AI 优化指南明确说明 `llms.txt` 对 Google 搜索既不帮助也不损害；仓库根目录也不是任何主流 AI 系统约定的读取路径。加一个没有消费者的文件只增加维护面，因此不加。若将来有具体平台声明读取仓库级 `llms.txt`，再按该平台的规范补。

## 6. 品牌与实体提及

当前为零：仓库新建，尚无 Wikipedia、Reddit、YouTube、LinkedIn 提及，也没有第三方文章链接。按 Ahrefs 的结论（提及与 AI 可见性的相关性高于外链），这比缺外链更值得补，但不能靠编造。

可执行且不造假的动作：

1. 在 skills.sh 收录后，用 `npx skills find obsidian` 验证检索可见性，并把结果记进本节。
2. 在相关仓库的 issue/讨论中给出真实使用报告（例如 kglite 的 vault 格式讨论），只写跑过的结果。
3. 把 fixture 验证脚本整理成可复现实验，供他人复跑并引用。

## 7. 段落级可引用性

首段即答案块（约 70 字）：

> obsidian-kglite 让 agent 用 Cypher 回答关于笔记、反向链接、标签、章节与段落的问题，并把图谱交给别的 agent 查询。它补的是 Obsidian 自身的一个空档：Obsidian 能按文本搜索、按链接浏览，却回答不了「哪些笔记没有任何语义链接」「哪一段提到了某个概念却没建双链」「这张参数表的哪一行承载了哪个事实」。

130–170 字是经验值而非 Google 规定；本仓库的做法是让每节开头先给结论，再给命令或依据，避免把结论压到节尾。

## 8. 服务端渲染检查

不适用。GitHub 在服务端把 README 渲染成 HTML，页面主体不依赖 JavaScript；同时 `raw.githubusercontent.com/KRPCT/obsidian-kglite/main/README.md` 返回纯文本。两条路径都不需要执行脚本。

## 9. 影响最大的五处改动

1. 默认 README 改中文并在首屏给定义，英文版保留为 `README.en.md`（已做）。
2. 加入可复现的原创数字（fixture 构建、真实 vault 冲突、漂移检查），替代泛泛的"强大/高效"（已做）。
3. FAQ 用用户原句提问，答案自足（已做）。
4. description 与 topics 覆盖中英检索词（description 已改中文，topics 保留英文 slug，因为 GitHub topics 不支持中文标点习惯）（已做）。
5. 建立"最后验证日期 + 适用版本"的刷新机制，随每次验证更新（已做：两份 README 顶部与 SOURCES.md）。

## 10. Schema 建议

GitHub 不给仓库页注入 JSON-LD 的入口，因此 Article / SoftwareApplication 之类的结构化数据在这里没有落点。等效做法是把实体信息写进可抓取的正文：项目名、定义、版本、许可、维护者、上游来源，README 已具备。若将来项目有独立站点，再补 `SoftwareApplication` 与 `Person`（作者）。

## 11. 仍需重排的内容

- 三篇长 references（`VAULT-FORMAT.md` 507 行、`CYPHER-COOKBOOK.md` 359 行）面向 agent 阅读，不追求网页段落长度；不为 GEO 强行拆分，避免破坏可查性。
- README 的"工作原理"一节可以再补一条失败路径（构建失败时会发生什么），目前只在 SKILL.md 的失败模式表里。
- 英文版缺少中文版里的术语对照表；若英文读者增长，再补一份英文术语表。

## 12. 未测量与边界

- 未测平台引用率、排名、AI 概览收录情况。
- 未测 GitHub 页面在 AI 模式下的实际摘录片段。
- 未做外链建设；本审计不含任何购买或交换链接的建议。
- 本文件是当前状态的记录，随每次验证或结构改动更新，不保留历史版本。
