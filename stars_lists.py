#!/usr/bin/env python3
"""
stars-lists —— GitHub Stars 自动分类工具

功能：
  sync      按 config.json 中的规则给 star 的仓库分类（首次全量 / 之后增量）
  plan      预览模式：只显示将要做什么，不做任何修改
  add       把一个仓库加入指定清单（追加语义，不动其他清单）
  lists     查看当前清单及条目数
  inbox     列出尚未分类的新 star 仓库

GitHub 的 star 清单没有官方 REST API，本工具使用 GitHub GraphQL 的内部
schema（createUserList / updateUserList / updateUserListsForItem），需要
token 具有 user scope（gh auth refresh -s user 即可）。

重要语义说明：
  updateUserListsForItem 是「全量替换」——传入的 listIds 会成为该仓库
  所属的全部清单。因此「追加到清单 X」的正确姿势是把仓库当前所属的
  清单 ID 全部取出来，加上 X 再整体写回。本工具的 add 和 sync 都遵守
  这一语义。
"""
import argparse
import json
import os
import subprocess
import sys
import time

API = "https://api.github.com/graphql"
VERSION = "1.0.0"

# --------------------------------------------------------------------------
# 基础设施
# --------------------------------------------------------------------------

def get_token():
    """token 来源优先级：环境变量 > gh CLI。"""
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok
    p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=False)
    if p.returncode != 0 or not p.stdout.strip():
        sys.exit("错误：拿不到 GitHub token。请先 gh auth login，或设置 GITHUB_TOKEN。")
    return p.stdout.strip()


class GQL:
    def __init__(self, token):
        self.token = token
        self.calls = 0

    def __call__(self, query, variables=None, retries=3):
        body = {"query": query, "variables": variables or {}}
        last = None
        for attempt in range(retries):
            p = subprocess.run(
                ["curl", "-s", "--max-time", "30",
                 "-H", f"Authorization: bearer {self.token}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(body, ensure_ascii=False),
                 API],
                capture_output=True, text=True, encoding="utf-8", check=False)
            self.calls += 1
            if p.returncode != 0 or not p.stdout.strip():
                last = RuntimeError(f"网络错误 rc={p.returncode} {p.stderr[:200]}")
                time.sleep(1.5 * (attempt + 1))
                continue
            d = json.loads(p.stdout)
            if "errors" in d:
                # 限流时等待重试
                msg = json.dumps(d["errors"], ensure_ascii=False)
                if "rate limit" in msg.lower() and attempt < retries - 1:
                    time.sleep(10)
                    continue
                raise RuntimeError(msg[:500])
            return d["data"]
        raise last or RuntimeError("GraphQL 请求失败")


# --------------------------------------------------------------------------
# 清单操作
# --------------------------------------------------------------------------

class Lists:
    def __init__(self, gql):
        self.gql = gql
        self._cache = None  # name -> {id, slug, isPrivate, description}

    def refresh(self):
        d = self.gql('query{viewer{lists(first:50){nodes{id name slug description isPrivate}}}}')
        self._cache = {n["name"]: n for n in d["viewer"]["lists"]["nodes"]}
        return self._cache

    @property
    def cache(self):
        if self._cache is None:
            self.refresh()
        return self._cache

    def ensure(self, name, description=None, is_private=False):
        """按名字拿清单 ID，不存在则创建。"""
        if name in self.cache:
            node = self.cache[name]
            if description and node.get("description") != description:
                self.gql("""mutation($id:ID!,$d:String!){updateUserList(input:{listId:$id,description:$d}){list{id}}}""",
                         {"id": node["id"], "d": description})
                node["description"] = description
            return node["id"]
        d = self.gql("""mutation($n:String!,$d:String,$p:Boolean){
                          createUserList(input:{name:$n,description:$d,isPrivate:$p}){list{id slug isPrivate}}
                        }""",
                     {"n": name, "d": description, "p": is_private})
        node = d["createUserList"]["list"]
        self.cache[name] = {"id": node["id"], "slug": node["slug"],
                            "isPrivate": node["isPrivate"], "description": description}
        return node["id"]

    def items_of(self, list_id):
        """取一个清单里的全部仓库名。"""
        names, after = [], None
        while True:
            q = ('query($id:ID!,$after:String){viewer{lists(first:50){nodes{id items(first:100,after:$after)'
                 '{pageInfo{hasNextPage,endCursor} nodes{... on Repository{nameWithOwner}}}}}}}')
            d = self.gql(q, {"id": list_id, "after": after})
            conn = None
            for n in d["viewer"]["lists"]["nodes"]:
                if n["id"] == list_id:
                    conn = n["items"]
                    break
            names += [x["nameWithOwner"] for x in conn["nodes"]]
            if conn["pageInfo"]["hasNextPage"]:
                after = conn["pageInfo"]["endCursor"]
            else:
                return names

    def memberships(self, repo_node_id):
        """仓库当前所属的全部清单 ID（updateUserListsForItem 全量替换语义需要）。"""
        # GraphQL 没有直接反向查询，走 item 路径：逐清单比对太贵，
        # 这里用一个技巧：调用 updateUserListsForItem 前不需要读——
        # 调用方传入 mode，要么 "replace"（明确指定），要么 "append"（先查后并）。
        # GitHub 没有公开该查询，因此 append 模式由调用方用 itemLists() 实现。
        raise NotImplementedError

    def item_lists(self, repo_node_id):
        """仓库当前所属的清单 ID 列表。实现：遍历自己的清单并比对成员。"""
        # 成员查询只有 items 正向分页。清单数量有限（几十个），逐清单检查成本可控。
        # 优化：先拉全部清单及其成员名，再按名字匹配。
        if not hasattr(self, "_member_map"):
            q = ('query{viewer{lists(first:50){nodes{id items(first:100){nodes{... on Repository{nameWithOwner}}}}}}}')
            d = self.gql(q)
            self._member_map = {}  # repo_name -> [list_id]
            for n in d["viewer"]["lists"]["nodes"]:
                for it in n["items"]["nodes"]:
                    self._member_map.setdefault(it["nameWithOwner"], []).append(n["id"])
        return self._member_map.get(None)  # placeholder，实际按名字查

    def lists_of_repo(self, repo_full_name):
        """仓库名 -> 所属清单 ID 列表（基于 _member_map）。"""
        if not hasattr(self, "_member_map"):
            self._build_member_map()
        return self._member_map.get(repo_full_name, [])

    def _build_member_map(self):
        q = ('query{viewer{lists(first:50){nodes{id name items(first:100){pageInfo{hasNextPage endCursor}'
             'nodes{... on Repository{nameWithOwner}}}}}}}')
        # 简化：假设每清单 <100 条；超过时分页（GitHub 未提供反向成员查询，
        # 这里只取第一页，超大清单需配合 items_of 逐清单分页）
        self._member_map = {}
        d = self.gql(q)
        for n in d["viewer"]["lists"]["nodes"]:
            for it in n["items"]["nodes"]:
                self._member_map.setdefault(it["nameWithOwner"], []).append(n["id"])
        return self._member_map

    def set_lists(self, repo_node_id, list_ids):
        """全量替换仓库所属清单。"""
        self.gql("""mutation($item:ID!,$lists:[ID!]!){
                      updateUserListsForItem(input:{itemId:$item,listIds:$lists}){lists{id}}
                    }""", {"item": repo_node_id, "lists": list_ids})

    def add_to(self, repo_full_name, repo_node_id, list_name):
        """追加语义：保留已有清单，再加一个新的。"""
        current = self.lists_of_repo(repo_full_name)
        target_id = self.cache[list_name]["id"]
        if target_id in current:
            return False  # 已在
        self.set_lists(repo_node_id, current + [target_id])
        if hasattr(self, "_member_map"):
            self._member_map.setdefault(repo_full_name, []).append(target_id)
        return True


def repo_node_id(gql, full_name):
    owner, name = full_name.split("/")
    d = gql('query($o:String!,$n:String!){repository(owner:$o,name:$n){id}}',
            {"o": owner, "n": name})
    r = d["repository"]
    if not r:
        sys.exit(f"错误：仓库不存在或无权限：{full_name}")
    return r["id"]


def starred_repos(gql):
    """全部 star 的仓库（名字 + node_id + star 时间）。"""
    out, after = {}, None
    while True:
        q = ('query($after:String){viewer{starredRepositories(first:100,after:$after,'
             'orderBy:{field:STARRED_AT,direction:ASC}){pageInfo{hasNextPage endCursor}'
             'edges{starredAt node{... on Repository{nameWithOwner id}}}}}}')
        d = gql(q, {"after": after})
        conn = d["viewer"]["starredRepositories"]
        for e in conn["edges"]:
            out[e["node"]["nameWithOwner"]] = {
                "id": e["node"]["id"], "starred_at": e["starredAt"]}
        if conn["pageInfo"]["hasNextPage"]:
            after = conn["pageInfo"]["endCursor"]
        else:
            return out


# --------------------------------------------------------------------------
# 分类规则（增量核心）
# --------------------------------------------------------------------------

class Rules:
    """关键词规则：name/语言/topics/description 命中即归类。

    config 结构：
      {
        "lists": [ {"name": "...", "description": "...", "private": false,
                    "any": ["kw1", "kw2"],       # 任一关键词命中（匹配 name/description/topics）
                    "languages": ["Python"]} ],  # 或者语言命中
        "extra_targets": ["owner/repo"],         # 强制加入的清单目标 {"repo": "list"} 也可以
        "my_list": {"name": "💎 我的项目", "owner": "Arimayuki03"}
      }
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def match(self, repo_meta):
        """返回命中的清单名列表。"""
        hits = []
        text = " ".join([
            repo_meta.get("name", ""),
            repo_meta.get("description") or "",
            " ".join(repo_meta.get("topics") or []),
        ]).lower()
        lang = repo_meta.get("language")
        for lst in self.cfg.get("lists", []):
            kws = [k.lower() for k in lst.get("any", [])]
            langs = lst.get("languages", [])
            if (kws and any(k in text for k in kws)) or (langs and lang in langs):
                hits.append(lst["name"])
        return hits


def repo_meta(gql, full_name):
    p = subprocess.run(
        ["curl", "-s", "-H", f"Authorization: bearer {get_token()}",
         f"https://api.github.com/repos/{full_name}"],
        capture_output=True, text=True, encoding="utf-8", check=False)
    r = json.loads(p.stdout)
    return {"name": full_name, "description": r.get("description"),
            "topics": r.get("topics") or [], "language": r.get("language")}


# --------------------------------------------------------------------------
# 命令
# --------------------------------------------------------------------------

def cmd_lists(args):
    # lists 只读远端清单，不依赖本地配置；但显式给了 --config 时校验它存在，
    # 避免用户拿它测试配置路径时静默通过。
    if getattr(args, "config", None) and args.config != "config.json":
        load_config(args.config)
    g = GQL(get_token())
    l = Lists(g)
    l.refresh()
    q = ('query{viewer{lists(first:50){nodes{name isPrivate items(first:100){totalCount}}}}}')
    d = g(q)
    for n in sorted(d["viewer"]["lists"]["nodes"], key=lambda x: -x["items"]["totalCount"]):
        flag = " [private]" if n["isPrivate"] else ""
        print(f"  {n['name']}{flag}: {n['items']['totalCount']}")


def cmd_inbox(args):
    """列出未分类的 star 仓库 + 规则建议。"""
    cfg = load_config(args.config)
    g = GQL(get_token())
    l = Lists(g)
    l._build_member_map()
    stars = starred_repos(g)
    rules = Rules(cfg)
    unsorted = []
    for full in stars:
        if full not in l._member_map:
            meta = repo_meta(g, full)
            hits = rules.match(meta)
            unsorted.append((full, hits))
    if not unsorted:
        print("收件箱是空的：所有 star 都已分类。")
        return
    print(f"未分类 {len(unsorted)} 个：")
    for full, hits in unsorted:
        suggest = f" -> {'、'.join(hits)}" if hits else " -> (无规则命中，需手动分类)"
        print(f"  {full}{suggest}")


def cmd_sync(args):
    """增量同步：按规则把新 star 分类；可选自动把自己的新仓库 star 并归入我的清单。"""
    cfg = load_config(args.config)
    g = GQL(get_token())
    l = Lists(g)
    l._build_member_map()
    stars = starred_repos(g)
    rules = Rules(cfg)

    # 确保清单存在
    list_ids = {}
    for lst in cfg.get("lists", []):
        list_ids[lst["name"]] = l.ensure(lst["name"], lst.get("description"),
                                         lst.get("private", False))
    my = cfg.get("my_list")
    if my:
        list_ids[my["name"]] = l.ensure(my["name"], my.get("description"), my.get("private", False))

    # 1) 自己名下的新仓库 -> star + 我的项目清单（append）
    my_added = 0
    if my and not args.skip_mine:
        owner = my.get("owner")
        p = subprocess.run(["gh", "api", f"/users/{owner}/repos?affiliation=owner&per_page=100&sort=full_name"],
                           capture_output=True, text=True, encoding="utf-8", check=False)
        for r in json.loads(p.stdout):
            if r["private"] and not my.get("include_private", False):
                continue
            full = r["full_name"]
            if full not in stars:
                subprocess.run(["gh", "api", "-X", "PUT", f"/user/starred/{full}"],
                               capture_output=True, check=False)
                stars[full] = {"id": r["node_id"], "starred_at": None}
                print(f"  ★ 已 star 自己的仓库：{full}")
            target = my["name"]
            lid = list_ids[target]
            cur = l.lists_of_repo(full)
            if lid not in cur:
                l.set_lists(stars[full]["id"], cur + [lid])
                l._member_map.setdefault(full, []).append(lid)
                my_added += 1
                print(f"  + {full} -> {target}")
    if my_added:
        print(f"自己的仓库处理完成：{my_added} 个新归入「{my['name']}」")

    # 2) 未分类的 star -> 规则匹配（append 语义，保留已有清单）
    new_hits, manual = 0, []
    for full, meta in sorted(((f, repo_meta(g, f)) for f in stars
                              if f not in l._member_map),
                             key=lambda x: x[0]):
        hits = rules.match(meta)
        if not hits:
            manual.append(full)
            continue
        cur = l.lists_of_repo(full)
        target_ids = cur + [list_ids[h] for h in hits if list_ids[h] not in cur]
        l.set_lists(stars[full]["id"], target_ids)
        for h in hits:
            l._member_map.setdefault(full, []).append(list_ids[h])
        new_hits += 1
        print(f"  + {full} -> {'、'.join(hits)}")
        time.sleep(0.2)

    print(f"\n同步完成：规则命中 {new_hits} 个，需人工 {len(manual)} 个")
    if manual:
        print("收件箱（无规则命中）：")
        for f in manual:
            print(f"  {f}")


def cmd_plan(args):
    """同 sync 但不做修改。"""
    cfg = load_config(args.config)
    g = GQL(get_token())
    l = Lists(g)
    l._build_member_map()
    stars = starred_repos(g)
    rules = Rules(cfg)
    todo = [(f, rules.match(repo_meta(g, f))) for f in stars if f not in l._member_map]
    my = cfg.get("my_list")
    if my:
        p = subprocess.run(["gh", "api", f"/users/{my['owner']}/repos?affiliation=owner&per_page=100"],
                           capture_output=True, text=True, encoding="utf-8", check=False)
        for r in json.loads(p.stdout):
            if not r["private"] and r["full_name"] not in stars:
                print(f"  [plan] 将 star 自己的仓库：{r['full_name']}")
    print(f"[plan] 将处理 {len(todo)} 个未分类仓库：")
    for full, hits in todo:
        print(f"  {full} -> {'、'.join(hits) if hits else '(无命中)'}")


def cmd_add(args):
    """手动把一个仓库加入清单（追加语义）。"""
    load_config(args.config)  # 校验配置存在；add 本身只需要清单名
    g = GQL(get_token())
    l = Lists(g)
    l.refresh()
    if args.list_name not in l.cache:
        sys.exit(f"清单不存在：{args.list_name}（可用 lists 命令查看）")
    l._build_member_map()
    nid = repo_node_id(g, args.repo)
    changed = l.add_to(args.repo, nid, args.list_name)
    print(f"  {'✓ 已加入' if changed else '· 本来就在'} {args.repo} -> {args.list_name}")


def load_config(path):
    if not os.path.exists(path):
        sys.exit(f"错误：找不到配置文件 {path}（参考 config.example.json）")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description=f"stars-lists v{VERSION} —— GitHub Stars 自动分类")
    ap.add_argument("--config", default="config.json", help="配置文件路径（默认 config.json）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # 允许 --config 写在子命令后面：SUPPRESS 让子命令未显式给出时不覆盖全局值
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    sub.add_parser("sync", parents=[common], help="增量同步：规则分类新 star（+ 可选自动 star 自己的仓库）")
    sub.add_parser("plan", parents=[common], help="预览将要做的变更")
    sub.add_parser("inbox", parents=[common], help="列出未分类仓库及规则建议")
    sub.add_parser("lists", parents=[common], help="查看清单及数量")
    p = sub.add_parser("add", parents=[common], help="把仓库加入清单（追加语义）")
    p.add_argument("repo")
    p.add_argument("list_name")

    args = ap.parse_args()
    if args.cmd == "sync":
        cmd_sync(args)
    elif args.cmd == "plan":
        cmd_plan(args)
    elif args.cmd == "inbox":
        cmd_inbox(args)
    elif args.cmd == "lists":
        cmd_lists(args)
    elif args.cmd == "add":
        cmd_add(args)


if __name__ == "__main__":
    main()
