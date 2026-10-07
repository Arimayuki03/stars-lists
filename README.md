<div align="center">

# ⭐ stars-lists

**给 GitHub Stars 建清单、自动分类、增量同步的命令行工具**

用 GitHub GraphQL 内部接口管理你的 [Stars Lists](https://github.com/stars)，
关键词规则自动归类新收藏，无需浏览器自动化。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/Arimayuki03/stars-lists/actions/workflows/ci.yml/badge.svg)](https://github.com/Arimayuki03/stars-lists/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Arimayuki03/stars-lists?include_prereleases&logo=github)](https://github.com/Arimayuki03/stars-lists/releases)
[![Stars](https://img.shields.io/github/stars/Arimayuki03/stars-lists?style=flat&logo=github)](https://github.com/Arimayuki03/stars-lists/stargazers)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Arimayuki03/stars-lists/pulls)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#-安装)

</div>

---

## 📋 目录

- [背景](#-背景)
- [功能特性](#-功能特性)
- [安装](#-安装)
- [快速开始](#-快速开始)
- [命令一览](#-命令一览)
- [增量规则](#-增量规则)
- [配置](#-配置)
- [工作原理](#-工作原理)
- [隐私与安全](#-隐私与安全)
- [FAQ](#-faq)
- [路线图](#-路线图)
- [贡献](#-贡献)
- [许可证](#-许可证)

## 🎯 背景

GitHub 的 [Stars Lists](https://github.com/stars)（星标清单）是官方给收藏分类的功能，
但它**没有公开 API**——手动一个个加清单非常繁琐。本项目逆向了 GitHub GraphQL schema
中管理清单的内部接口（`createUserList` / `updateUserList` / `updateUserListsForItem`），
封装成一个零依赖的 Python CLI，实现：

1. **首次全量分类** —— 按关键词规则把已有 star 全部归入清单；
2. **日常增量同步** —— 以后每 star 新仓库，跑一次 `sync` 即自动归类。

> 本仓库作者的真实收藏分类即由本工具维护，见
> [config.json 的规则设计](#-配置)。

## ✨ 功能特性

| 特性 | 说明 |
|---|---|
| 🔍 关键词规则 | 按仓库名 / 描述 / topics / 主语言命中清单，不区分大小写 |
| 📥 收件箱 | `inbox` 列出未分类的 star 并给出规则建议，不漏掉任何一个 |
| 🧪 预览模式 | `plan` 只展示将要发生的变更，零风险 |
| ➕ 追加语义 | `add` 保留仓库已属清单，只追加新清单（正确处理了 GitHub 的全量替换坑） |
| 💎 自动收藏自己 | `sync` 可自动 star 你名下的新仓库并归入「我的项目」清单 |
| 🔒 私密清单 | 支持创建仅自己可见的清单 |
| 🔁 限流重试 | 内置网络重试与 GraphQL rate limit 退避 |
| 📦 零依赖 | 纯 Python 标准库，只需要 `gh` CLI 或一个 token |

## 📦 安装

前置条件（二选一）：

- **[GitHub CLI](https://cli.github.com/)** 已安装并登录（推荐）：
  ```bash
  gh auth login
  # 清单接口需要 user scope，如果之前登录过，需要补一次授权：
  gh auth refresh -s user
  ```
- 或设置环境变量 `GITHUB_TOKEN`（需 `user` scope）。

然后克隆本仓库：

```bash
git clone https://github.com/Arimayuki03/stars-lists.git
cd stars-lists
```

无需 `pip install` —— 纯标准库，开箱即用（Windows / macOS / Linux 均可）。

## 🚀 快速开始

```bash
# 1. 复制一份配置，改成你自己的规则
cp config.example.json config.json

# 2. 预览将要发生什么（不做任何修改）
python stars_lists.py plan

# 3. 看看哪些 star 还没分类、规则会怎么分
python stars_lists.py inbox

# 4. 确认无误后执行增量同步
python stars_lists.py sync

# 5. 查看清单现状
python stars_lists.py lists
```

## 🧰 命令一览

```
stars_lists.py [--config config.json] <command>

  sync     增量同步：规则分类新 star（可选自动 star 自己的新仓库）
  plan     预览将要做的变更，不做修改
  inbox    列出未分类的 star 仓库及规则命中建议
  lists    查看当前清单及条目数
  add      把仓库加入清单：python stars_lists.py add owner/repo "清单名"
```

> 所有命令默认读取当前目录的 `config.json`，可用 `--config` 指定其他路径。

## ⚙️ 增量规则

增量同步的核心思想：**清单成员是真相源，规则只处理「尚未分类」的仓库**。

每次 `sync` 的流程：

```
拉取全部 star ──► 拉取全部清单成员 ──► 差集 = 收件箱
                                        │
              ┌─────────────────────────┤
              ▼                         ▼
     规则命中关键词？              无命中 → 打印提示，等你手动
              │                            python stars_lists.py add ...
              ▼
   追加进对应清单（保留已属清单）
```

- **追加而非替换**：GitHub 的 `updateUserListsForItem` 是全量替换语义——
  传入的清单 ID 会成为仓库的*全部*所属清单。本工具在追加前会先取回仓库
  当前所属清单，合并后再写回，保证「一个仓库同时在 💎我的项目 和 🤖AI编程代理」
  这类多清单归属不被破坏。
- **自动 star 自己的仓库**：配置 `my_list` 后，`sync` 会检查你名下是否有
  未 star 的新仓库，自动 star 并归入你的清单（私有仓库默认跳过）。
- **清单自动创建**：规则里写了但还不存在的清单会自动创建（含描述与私密标记）。

## 📄 配置

`config.json`（被 `.gitignore` 忽略，规则是你的个人数据）：

```jsonc
{
  "lists": [
    {
      "name": "🤖 AI 编程代理与技能",       // 清单名（支持 emoji）
      "description": "AI 编程代理与技能",   // 清单简介（公开可见）
      "private": false,                     // 是否私密清单
      "any": ["claude-code", "codex", "agent-skills"],  // 关键词：命中 name/description/topics
      "languages": ["TypeScript"]           // 可选：主语言命中
    }
    // ...更多清单
  ],
  "my_list": {                              // 可选：自动 star 自己的仓库
    "name": "💎 我的项目",
    "description": "我的原创项目",
    "owner": "your-username",
    "include_private": false                // 是否把私有仓库也 star 进去
  }
}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `lists[].name` | ✅ | 清单名，不存在会自动创建 |
| `lists[].description` | ➖ | 清单简介，公开页面可见 |
| `lists[].private` | ➖ | 默认 `false` |
| `lists[].any` | ✅ | 关键词数组，任一命中即归类（大小写不敏感，子串匹配） |
| `lists[].languages` | ➖ | 主语言数组，命中即归类 |
| `my_list.name` / `owner` | ➖ | 启用「自动 star 自己仓库」必填 |

完整示例见 [config.example.json](config.example.json)。

## 🔬 工作原理

GitHub 未公开 star 清单的 REST API，但其 **GraphQL schema 内部已实现**。
本项目通过 schema 内省确认了以下接口（均需要 token 具有 `user` scope）：

| GraphQL 接口 | 用途 |
|---|---|
| `viewer.lists` | 枚举自己的清单 |
| `createUserList` | 创建清单（名称/描述/私密） |
| `updateUserList` | 更新清单（如改描述） |
| `updateUserListsForItem` | 设置仓库所属清单（**全量替换**语义） |
| `viewer.starredRepositories` | 枚举全部 star（含 node id） |
| `viewer.suggestedListNames` | GitHub 官方建议的清单名 |

⚠️ 兼容性提示：这些是 GitHub 的**内部 schema**，未被官方文档承诺稳定，
未来字段可能变化。本工具在遇到 schema 错误时会直接报错而非静默失败。

## 🔐 隐私与安全

- **token 不落盘**：仅从 `GITHUB_TOKEN` 环境变量或 `gh auth token` 读取，
  不写入任何文件、不出现在命令行参数。
- **你的规则即隐私**：`config.json`（含你的个人分类口味）默认被 `.gitignore`
  忽略，仓库里只提供脱敏的 `config.example.json`。
- **私密清单**：`"private": true` 的清单只有你自己可见，不会出现在公开主页。
- **最小权限**：只需要 `user` scope（清单接口的硬性要求）+ `repo`
  （`gh` 默认已含）；不需要 `delete_repo` 等高危权限。

## ❓ FAQ

<details>
<summary><b>为什么不用官方 API？</b></summary>

因为官方没有。GitHub REST / GraphQL 的公开文档里均无 star 清单接口，
只有 GraphQL 内部 schema 有实现。本仓库所有操作都走这个内部接口。
</details>

<details>
<summary><b>会不会把我的清单搞乱？</b></summary>

本工具把「全量替换」语义作为一等公民处理：所有追加操作都先读后写。
如果不确定，先跑 `plan` 看预览。另外清单成员随时可以在网页上手动调整，
本工具不会删除任何清单或取消任何 star。
</details>

<details>
<summary><b>Internal API 失效了怎么办？</b></summary>

GraphQL schema 变化时工具会显式报错（不会静默出错数据）。
届时可重新内省 schema（见 `Lists` 类的查询语句）并提 PR 适配。
</details>

<details>
<summary><b>Windows 下的中文乱码？</b></summary>

脚本内部已用 UTF-8 包装 stdout/stderr；建议在终端执行
`chcp 65001` 或使用 Windows Terminal。
</details>

## 🗺️ 路线图

- [ ] `remove` 命令：从清单移除仓库
- [ ] `rename` / `delete` 清单管理
- [ ] 从现有清单反推 `config.json`（bootstrap 你的规则）
- [ ] GitHub Actions 定时增量同步
- [ ] 打包发布到 PyPI

## 🤝 贡献

欢迎 Issue 与 PR！提交前请：

```bash
pip install -r requirements-dev.txt
ruff check stars_lists.py
```

## 📜 许可证

[MIT](LICENSE) © 2026 Arimayuki03

---

<div align="center">

**[⭐ Star 这个项目](https://github.com/Arimayuki03/stars-lists/stargazers)** 如果你觉得有用 ·
**[📋 反馈问题](https://github.com/Arimayuki03/stars-lists/issues)**

</div>
