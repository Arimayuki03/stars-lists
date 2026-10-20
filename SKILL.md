---
name: stars-lists
description: 用 GitHub Stars Lists 内部 GraphQL 接口管理 GitHub 星标收藏：首次全量关键词自动分类、日常增量同步（sync）、收件箱查漏（inbox）、预览变更（plan）、把仓库加入清单（add）。当用户要求"整理 GitHub stars / 给星标建清单 / 分类收藏的仓库 / sync 一下 stars / star 清单增量同步 / 查看清单 / 把某某仓库加进清单"时使用。
---

# stars-lists — GitHub Stars 清单管理

零依赖 Python CLI，逆向 GitHub GraphQL 内部接口（`createUserList` / `updateUserList` / `updateUserListsForItem`）管理 [Stars Lists](https://github.com/stars)。无需浏览器自动化。

所有命令在本技能目录（即项目根目录）下执行：

```bash
python stars_lists.py [--config config.json] <command>
```

## 前置条件（二选一）

- `gh` CLI 已登录，且具有 `user` scope（清单接口必需）。若之前登录过但缺 scope：
  `gh auth refresh -s user`
- 或环境变量 `GITHUB_TOKEN`（需 `user` scope）。

## 命令

| 命令 | 作用 | 风险 |
|---|---|---|
| `plan` | 预览将要发生的变更，不做任何修改 | 零风险 |
| `inbox` | 列出未分类的 star 及规则命中建议 | 零风险 |
| `sync [--skip-mine]` | 增量同步：按 config.json 规则归类新 star；可自动 star 自己的新仓库并归入 `my_list` 清单（`--skip-mine` 跳过此步） | 写操作 |
| `lists` | 查看当前清单及条目数 | 零风险 |
| `add <owner/repo> "清单名"` | 把指定仓库加入清单 | 写操作 |

## 安全规则

1. **任何写操作前先跑 `plan`**：向用户展示将要做的变更，确认后再 `sync` / `add`。
2. **inbox 里无命中规则的仓库不要强行归类**：把建议展示给用户，由用户决定手动 `add` 到哪个清单，或让用户补规则。
3. **config.json 是用户个人数据**（已被 .gitignore 忽略）：不要把它的规则内容提交或外发；用户想改分类规则时，编辑 config.json 的 `lists[].any` / `languages` 关键词。
4. token 只从 `GITHUB_TOKEN` 或 `gh auth token` 读取，不要落盘、不要打印。

## 行为要点（不需要用户操心，但 agent 要知道）

- GitHub 的 `updateUserListsForItem` 是**全量替换**语义；本工具写回前会取回仓库现有清单并合并，实现"追加"——不要绕过工具直接调 GraphQL。
- 规则里写了但尚不存在的清单会自动创建（含描述与私密标记）。
- 遇到 GraphQL schema 报错会直接失败（内部接口无稳定性承诺），此时如实报告，不要重试超过内置的限流退避次数。
