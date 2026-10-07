# Changelog

本项目的所有重要变更都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-10-07

### Added

- 首个发布版本。
- `sync`：增量同步——按关键词/语言规则把新 star 的仓库分类到清单；
  可选自动 star 自己名下的新仓库并归入「我的项目」清单。
- `plan`：预览模式，只显示将要发生的变更，不做任何修改。
- `inbox`：列出尚未分类的 star 仓库，并给出规则命中建议。
- `lists`：查看当前所有清单及条目数。
- `add`：把指定仓库追加到指定清单（保留其已属清单，追加语义）。
- 通过 GitHub GraphQL 内部接口管理 star 清单（`createUserList` /
  `updateUserList` / `updateUserListsForItem`），无需浏览器自动化。
- 关键词规则配置：`config.json` 中按清单配置命中关键词（匹配仓库名、
  描述、topics）与主语言。
- 正确处理 `updateUserListsForItem` 的全量替换语义：追加时先取仓库
  当前所属清单，合并后再写回。

### Security

- token 仅从环境变量 `GITHUB_TOKEN` 或 `gh auth token` 读取，不落盘、
  不出现在命令行参数中。
