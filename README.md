# obsidian-kglite

**把 Obsidian vault 读成可查询的知识图谱的 agent skill。**

obsidian-kglite 让 agent 用 Cypher 回答关于笔记、反向链接、标签、章节与段落的问题，并把图谱交给别的 agent 查询。它补的是 Obsidian 自身的一个空档：Obsidian 能按文本搜索、按链接浏览，却回答不了「哪些笔记没有任何语义链接」「哪一段提到了某个概念却没建双链」「这张参数表的哪一行承载了哪个事实」。vault 始终是唯一事实来源，图谱只是可随时重建的透镜，构建过程不写入 vault。

[English](README.en.md) · 适用 kglite 0.21.2 / Obsidian 1.14.5 · 最后验证 2026-10-26

![vault 到图谱的流程](docs/architecture.svg)

## 它做什么

| 能力 | 具体动作 | 产物 |
| --- | --- | --- |
| 度量 | 孤儿笔记、断链、重复词干、标签枢纽、章节与段落统计 | `okf check` 报告与 Cypher 结果 |
| 修复 | 以证据为前置条件提出加链建议，改完复测同一组指标 | 可回滚的单条笔记修改 |
| 服务 | 把图谱以 MCP 暴露，技能与参数化查询随 vault 一起分发 | `kglite-mcp-server` 与 `.kglite/recipes` |
| 写回 | 把图变成 Obsidian 能看的关系图、反向链接索引，或整份可核对的导出 | `.canvas`、`Backlinks.md`、sealed export |

## 快速开始

```bash
uv tool install kglite==0.21.2          # 需要 Python 3.10+，CLI 与 Python API 同一个包
mkdir -p .kglite-out
kglite okf check VAULT --strict         # 只读校验，退出码非零即不合规
kglite okf build VAULT -o .kglite-out/vault.kgl
kglite query .kglite-out/vault.kgl "MATCH (n) WHERE n.file_path IS NOT NULL RETURN count(*) AS notes" --format json
kglite okf status VAULT --graph .kglite-out/vault.kgl
```

也可以走封装脚本，它替你挡掉三个常见错误（输出目录不存在、图谱写进 vault、一次查两条语句）：

```bash
python skills/obsidian-kglite/scripts/vault_graph.py build VAULT
python skills/obsidian-kglite/scripts/vault_report.py VAULT --out .kglite-out/health.md
```

## 安装

```bash
# 推荐：npx skills（全局装到 ~/.agents/skills，并在支持的 agent 里建符号链接）
npx skills add KRPCT/obsidian-kglite@obsidian-kglite -g -y

# Claude Code 插件市场
/plugin marketplace add KRPCT/obsidian-kglite
/plugin install obsidian-kglite@obsidian-kglite

# 手动：克隆后拷进任意 skills 目录（Codex、OpenCode 等）
git clone https://github.com/KRPCT/obsidian-kglite.git
cp -r obsidian-kglite/skills/obsidian-kglite ~/.agents/skills/
```

仓库遵循 [Agent Skills](https://agentskills.io/specification) 的 `skills/<name>/SKILL.md` 布局，这也是 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 使用的组织方式，所以 `npx skills add <owner>/<repo>@<skill>` 可以直接识别。

## 它和现成做法有什么不同

| 做法 | 能回答的问题 | 答不了的问题 |
| --- | --- | --- |
| Obsidian 全局搜索 | 某个词出现在哪里 | 哪些笔记之间没有任何语义链接 |
| [obsidian-cli](https://help.obsidian.md/cli)（应用自带 CLI） | 读写笔记、查反向链接、跑插件 | 跨笔记的图结构统计、表格行级事实、批量度量 |
| 手写脚本扫 Markdown | 自己定义的任何规则 | 链接解析阶梯、标签枢纽、章节与段落的两级 id |
| KGLite 图谱（本仓库） | 上述全部，且用同一条查询语言 | 不改动原文，也不替代 Obsidian 的写作体验 |

两者的分工是清楚的：写完笔记用 Obsidian，问结构问题用图谱。

## 工作原理

1. `okf check` 用与构建完全相同的一次读取来做校验，读完把图丢掉——它不是第二意见。
2. `okf build` 生成 `.kgl`，并把报告写到 stderr、把路径写到 stdout；图谱默认落在 vault 之外。
3. 笔记的文件夹决定标签，文件名决定 id，frontmatter 里指向笔记的值变成边，`#标签` 汇入标签枢纽。
4. 在 `.kglite/vault.yaml` 里声明 `structure:` 后，标题变成 Section、段落包成 Chunk、callout 变成 Note、编号列表变成 Procedure 与 ProcedureStep、表格每行成为一个节点。
5. 之后所有问题都用 Cypher 问，改完笔记再跑一次 `check` 与 `status`。

## 双向链路：从图谱写回 Obsidian

只读图谱只解决一半问题。另一半是让图回到 Obsidian 里，让读者看见关系，同时不污染被测的图。三条路径副作用不同，按需要选：

| 目标 | 命令 | 写进 vault 的东西 | 下次构建的影响 |
| --- | --- | --- | --- |
| 在 Obsidian 里看关系图 | `python scripts/vault_canvas.py VAULT` | `Graph.canvas` | 无（canvas 不被解析） |
| 看每篇笔记的入链与出链 | `python scripts/vault_writeback.py backlinks VAULT` | `Backlinks.md` | 无（`kg_skip: true`） |
| 迁移或重构整份 vault | `python scripts/vault_writeback.py export G OUT --source-root VAULT` | 一棵新树，不覆盖原地 | 那棵树是新的 vault |
| 改某一条链接 | Obsidian CLI 或直接编辑文件 | 笔记本体 | 会变，这是设计 |

两条让往返可信的规则：

- **先补声明，再去重。** 导出不写 `.kglite/vault.yaml`；而 `heading_edges` 声明的类型，导出器用它自己的散文扫描器复现不出来，于是会写一条 frontmatter 列表，下次构建就多出同一条关系。`scripts/vault_roundtrip.py` 把「复制声明」和「删掉重复的 frontmatter 键」都做掉，然后再证明结果。
- **不要往被扫描的笔记里追加生成的链接。** 写在笔记里的反向链接就是真实的边，每跑一次都会改变生成它的那份报告。一篇 `kg_skip` 索引笔记承载同样的信息，并且有不动点。

```bash
python scripts/vault_roundtrip.py VAULT
```

```text
round trip: PASS
  ok   export_deterministic
  ok   note_set_preserved
  ok   bodies_preserved
  ok   semantic_edges_preserved
  ok   dangling_links_preserved
  ok   fixed_point
  ok   structure_rebuilt
  notes 5 -> 5; semantic edges 5 -> 5
  seal removed 1 duplicated frontmatter key(s) in 1 file(s); declarations copied: vault.yaml
```

双向关系本身就用两条查询表达：入链与出链度数、以及互为链接的配对（`references/CYPHER-COOKBOOK.md` 第 3 节）。写回机制、失败模式与「哪些东西永远留在 vault 里」见 `references/WRITEBACK.md`。

## 已验证的事实

下面这些数字来自本仓库的验证运行，可复现（详见 `skills/obsidian-kglite/references/SOURCES.md`）。

| 事实 | 数值 | 来源 |
| --- | --- | --- |
| fixture vault（5 篇笔记）构建结果 | 38 个节点、11 个 Chunk、0 error、1 个悬空链接警告 | `verify-fixture.log` |
| 同一 fixture 上的孤儿笔记 | 1 篇（无任何语义边） | 孤儿查询 |
| 一个真实的 26 篇笔记 vault | 抓出 14 篇 `README` 词干冲突（构建期 error），1 处断链 | `okf check` 输出 |
| 内联上游材料的漂移检查 | 两篇文件均为 `CURRENT` | `check_upstream.py` |
| 写回 canvas 后的图 | 节点与边计数完全不变（canvas 不被解析） | 写回前后 `okf check` |
| 反向链接索引重跑 | 文件字节相同（幂等），图计数不变 | `vault_writeback.py` 两次运行 |
| sealed 导出往返 | 7 项检查全过，5 篇笔记与 5 条语义边原样回来 | `vault_roundtrip.py` |

## 常见问题

### 会改动我的 vault 吗？

不会。构建是只读的：`okf build` 把图写到 vault 之外，`okf check` 读完即弃。唯一会写入 vault 的是 `okf open`，因为它把缓存放在 `VAULT/.kglite/graph.kgl`；需要绝对干净时用 `--cache ../out/cache.kgl` 或 `--cache none`。改笔记只发生在你或 agent 显式编辑文件、或通过 Obsidian CLI 写入时。

### 需要 Obsidian 一直开着吗？

只有走 Obsidian CLI 的编辑路径需要。建图、查图、健康报告全部直接读文件，不依赖应用运行。CLI 路径的典型用途是让 Obsidian 自己的索引与反向链接缓存同步更新。

### 支持多大的 vault？

没有仓库层面的上限，代价主要在构建时间与内存：`okf build` 每次都完整读一遍笔记，`okf open` 会按指纹复用缓存。缓存按 `source_root` 打戳，所以复制或移动 vault 会触发一次重建，这是设计而非缺陷。

### kglite 和 Obsidian 插件有什么区别？

Obsidian 插件运行在应用内部，服务写作与渲染；kglite 是独立的 Python 包与 CLI，把 vault 读成属性图后提供 Cypher、图算法、MCP 服务。两者共享同一批 Markdown 文件，互不接管对方职责。

### 中文笔记和中文标签支持吗？

支持。标签、标题、正文按 UTF-8 读取；中文标签照常进入标签枢纽，大小写折叠规则对中文无副作用。Cypher 里的字符串按原样匹配，无需转码。唯一要注意的是文件名：词干即 id，重名会触发词干冲突规则，中文词干同样适用。

### 数据会上传到哪里？

不会。`kglite` 是本地嵌入式引擎，建图与查询都在本机完成；MCP 服务默认也只监听本机。是否把 vault 同步到别处由你决定，与本 skill 无关。

## 中文术语与图模型对照

| 你会怎么说 | 图里的对象 | 查询入口 |
| --- | --- | --- |
| 孤儿笔记 / 孤岛笔记 | 没有任何语义边的笔记 | `file_path IS NOT NULL` 加度数过滤 |
| 断链 / 空链接 | `_provisional` 桩节点 | `MATCH (n {_provisional: true})` |
| 双链 / 反向链接 | 带类型的边与 `LINKS_TO` | `(m)-[r]->(n)` |
| 标签体系 / 标签树 | `Tag` 枢纽 | `(t:Tag)<-[:TAGGED]-(n)` |
| 章节 / 小节 | `Section` | `HAS_SECTION` 与 `PARENT_SECTION` |
| 段落块 / 引用块 | `Chunk` | `text CONTAINS` |
| 提示框 / 警告块 | `Note` 与 `kind` | `MATCH (n:Note)` |
| 参数表 / 字段表 | 表格行节点 | `structure.tables` 规则 |

## 仓库结构

```text
skills/obsidian-kglite/
  SKILL.md                     入口：建模规则、四步循环、失败模式、验收清单
  references/
    VAULT-FORMAT.md            规范全文的压缩版，带章节号
    CYPHER-COOKBOOK.md         按问题分组的查询，每条都执行过
    ANNOTATIONS.md             五种注解与读回它们的查询
    LINK-GRAPH.md              链接修复协议：两信号规则与反模式
    SERVING.md                 MCP、.kglite/skills、.kglite/recipes、输出预算
    OBSIDIAN-CLI.md            内联的 Obsidian CLI 参考（随上游校验）
    OBSIDIAN-MARKDOWN.md       内联的 Obsidian Markdown 要点（随上游校验）
    SOURCES.md                 来源、版本、已验证与仅文档的边界
  scripts/                     七个脚本：封装、健康报告、漂移检查、本地部署、canvas、写回、往返校验
  assets/                      vault.yaml 起始配置、注解模板、vault 内 skill 模板
  evals/evals.json             三条测试提示
docs/                          架构图与 GEO 审计
```

## 维护与更新

```bash
# 改完仓库后同步到本机技能目录
python skills/obsidian-kglite/scripts/install_local.py --force

# 检查内联的 Obsidian 材料是否落后于上游
python skills/obsidian-kglite/scripts/check_upstream.py
```

漂移出现时重新内联对应段落，并更新文件头的 `upstream-sha256`，两件事放在同一次提交里。

## 许可与致谢

MIT，见 [LICENSE](LICENSE)。

内联的 Obsidian CLI 与 Markdown 参考来自 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)（MIT，© Steph Ango）；链接修复的思路来自 [galaxy-dawn/claude-scholar](https://github.com/galaxy-dawn/claude-scholar) 的 `obsidian-link-graph`；把思路变成可度量查询的部分由本仓库负责。

仓库的 GEO 自审记录见 [docs/GEO-ANALYSIS.md](docs/GEO-ANALYSIS.md)。

