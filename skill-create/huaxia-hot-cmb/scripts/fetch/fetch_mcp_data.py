#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_mcp_data.py — MasterGo MCP 原始数据抓取脚本（独立 MCP 客户端）

作用
    以官方 mcp Python SDK 作为 stdio 客户端，拉起 `npx @mastergo/magic-mcp`
    子进程，按固定 7 步序列调用全部可用工具，做到样式数据零丢失，
    把每个工具的原始响应 + 一份合并后的完整 JSON 落盘到 data/raw/。

序列（依据 doc 的《MasterGo MCP 数据提取方案》）
    Step 1  getDsl              完整 DSL（必须最先调，否则服务器进入分段缓存态，
                                getDsl 会返回 skipped:true，path.data / textRuns 永久丢失）
    Step 2  getMeta             站点/页面级配置规则
    Step 3  getDesignSections   概览（不传 sectionIndex）→ 得到 totalSections
    Step 4  getDesignSections   逐段拉取（sectionIndex=0..N-1，按批并发）
    Step 5  getDesignSvgs       补回被 Section 剥离的 PATH svgHtml
            getDesignTexts      补回被占位符替换的长文本原文
            extractSvg          PATH 几何 + paint 合成带色 SVG
    Step 6  getComponentLink    仅当 getDsl 返回 componentDocumentLinks 非空
    Step 7  getD2c              补 blendMode/rotation/clip 等 DSL 不提供的渲染属性
                                （404 / code 10009 记入 unresolved 并跳过，不阻塞）

用法
    python fetch_mcp_data.py                 # 读 config/ 下配置执行完整抓取
    python fetch_mcp_data.py --check         # 只校验配置/依赖/URL 解析，不联网
    python fetch_mcp_data.py --design-url ... --token ...   # 命令行覆盖配置

配置
    config/project.config.json   designUrl 或 fileId+rootNodeId、apiBaseUrl 等
    config/local.secret.json     mcpToken（或环境变量 MG_MCP_TOKEN）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

# ----------------------------------------------------------------------------
# 路径：脚本位于 <SKILL_ROOT>/scripts/fetch/fetch_mcp_data.py
# ----------------------------------------------------------------------------
SKILL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = SKILL_ROOT / "config"
PROJECT_CONFIG = CONFIG_DIR / "project.config.json"
SECRET_CONFIG = CONFIG_DIR / "local.secret.json"

# 规范工具名（去掉 mcp__ 前缀、小写）→ 运行期真实工具名 的映射在连接后建立
CANON = lambda n: re.sub(r"^mcp__", "", str(n)).lower()


# ============================================================================
# 配置加载与 ID 解析
# ============================================================================
def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_ids_from_url(url: str) -> dict:
    """从 MasterGo 设计链接解析 fileId / layerId / sourceLayerId / shortLink。

    支持：
      https://mastergo.com/file/<fileId>?layer_id=<layerId>&source_layer_id=<sid>
      https://mastergo.com/goto/<short>            → 短链
      ...?file=<fileId>&layerId=<layerId>          → 兼容 query 形式
    """
    out = {"fileId": "", "layerId": "", "sourceLayerId": "", "shortLink": ""}
    if not url:
        return out
    if "/goto/" in url:
        out["shortLink"] = url
        return out

    parsed = urlparse(url)
    q = parse_qs(parsed.query)

    m = re.search(r"/file/([^/?#]+)", parsed.path)
    if m:
        out["fileId"] = unquote(m.group(1))
    elif q.get("file"):
        out["fileId"] = unquote(q["file"][0])
    elif q.get("fileId"):
        out["fileId"] = unquote(q["fileId"][0])

    for key in ("layer_id", "layerId", "layer"):
        if q.get(key):
            out["layerId"] = unquote(q[key][0])
            break

    for key in ("source_layer_id", "sourceLayerId"):
        if q.get(key):
            out["sourceLayerId"] = unquote(q[key][0])
            break

    return out


def resolve_config(args: argparse.Namespace) -> dict:
    proj = _load_json(PROJECT_CONFIG)
    secret = _load_json(SECRET_CONFIG)

    design_url = args.design_url or proj.get("designUrl", "")
    ids = parse_ids_from_url(design_url) if design_url and "<" not in design_url else {}

    file_id = args.file_id or proj.get("fileId") or ids.get("fileId", "")
    layer_id = args.layer_id or proj.get("rootNodeId") or ids.get("layerId", "")
    source_layer_id = proj.get("sourceLayerId") or ids.get("sourceLayerId", "")
    short_link = ids.get("shortLink", "")

    token = (
        args.token
        or secret.get("mcpToken")
        or os.environ.get("MG_MCP_TOKEN")
        or os.environ.get("MASTERGO_API_TOKEN")
        or ""
    )
    if token.startswith("<") or token in ("", "YOUR_MASTERGO_PERSONAL_ACCESS_TOKEN"):
        token = ""

    api_base = args.url or proj.get("apiBaseUrl") or "https://mastergo.com"
    package = proj.get("mcpPackage") or "@mastergo/magic-mcp"
    batch = int(args.section_batch or proj.get("sectionBatchSize") or 4)

    raw_dir = SKILL_ROOT / (proj.get("output", {}).get("rawDir") or "data/raw")

    return {
        "projectName": proj.get("projectName", "mastergo-project"),
        "designUrl": design_url,
        "fileId": file_id,
        "layerId": layer_id,
        "sourceLayerId": source_layer_id,
        "shortLink": short_link,
        "token": token,
        "apiBaseUrl": api_base.rstrip("/"),
        "mcpPackage": package,
        "sectionBatchSize": max(1, batch),
        "rawDir": raw_dir,
    }


def validate_config(cfg: dict) -> list[str]:
    errs = []
    if not cfg["token"]:
        errs.append("缺少 MasterGo token（config/local.secret.json 的 mcpToken 或环境变量 MG_MCP_TOKEN）")
    has_ids = cfg["fileId"] and cfg["layerId"]
    if not has_ids and not cfg["shortLink"]:
        errs.append("缺少 fileId+layerId，且没有短链：请在 project.config.json 填 designUrl 或 fileId+rootNodeId")
    if cfg["shortLink"] and not has_ids:
        errs.append(
            "只提供了短链：getMeta / getD2c 需要显式 fileId+layerId，将被跳过。"
            "建议用完整链接 https://mastergo.com/file/<fileId>?layer_id=<layerId>"
        )
    return errs


# ============================================================================
# 工具响应解析辅助
# ============================================================================
def result_to_record(result: Any) -> dict:
    """把 CallToolResult 转成 {isError, text, json}。"""
    is_error = bool(getattr(result, "isError", False))
    texts: list[str] = []
    for item in getattr(result, "content", []) or []:
        t = getattr(item, "text", None)
        if t is not None:
            texts.append(t)
        elif isinstance(item, dict) and "text" in item:
            texts.append(item["text"])
    raw_text = "\n".join(texts)
    parsed = None
    if raw_text.strip():
        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError):
            parsed = None
    return {"isError": is_error, "text": raw_text, "json": parsed}


def deep_find_first(obj: Any, key: str) -> Any:
    """在嵌套结构里深度优先找第一个 key 的值。"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = deep_find_first(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = deep_find_first(v, key)
            if found is not None:
                return found
    return None


def extract_component_links(dsl_json: Any) -> list[str]:
    """从 getDsl 响应里提取 componentDocumentLinks，返回去重后的 URL 列表。"""
    raw = deep_find_first(dsl_json, "componentDocumentLinks")
    links: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                links.append(item)
            elif isinstance(item, dict):
                for k in ("url", "link", "documentLink", "href"):
                    if item.get(k):
                        links.append(item[k])
                        break
    seen, uniq = set(), []
    for u in links:
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def extract_total_sections(overview_json: Any) -> int:
    v = deep_find_first(overview_json, "totalSections")
    if isinstance(v, int) and v >= 0:
        return v
    if isinstance(v, str) and v.isdigit():
        return int(v)
    secs = deep_find_first(overview_json, "sections")
    if isinstance(secs, list):
        return len(secs)
    return 0


# ============================================================================
# MCP 客户端封装
# ============================================================================
class McpRunner:
    def __init__(self, session, tool_index: dict[str, str], log):
        self.session = session
        self.tool_index = tool_index          # canonical -> real name
        self.log = log

    def real_name(self, canonical: str) -> str | None:
        return self.tool_index.get(CANON(canonical))

    async def call(
        self,
        canonical: str,
        args: dict,
        *,
        allowed_props: dict[str, set[str]],
        timeout: float = 120.0,
    ) -> dict:
        real = self.real_name(canonical)
        if not real:
            return {"isError": True, "text": f"tool not found: {canonical}", "json": None,
                    "_missing": True}
        # 只保留该工具 inputSchema 声明的参数，避免版本差异导致的多余字段报错
        props = allowed_props.get(real)
        if props:
            args = {k: v for k, v in args.items() if k in props and v not in (None, "")}
        else:
            args = {k: v for k, v in args.items() if v not in (None, "")}
        try:
            result = await self.session.call_tool(
                real, args, read_timeout_seconds=timedelta(seconds=timeout)
            )
            rec = result_to_record(result)
            rec["_args"] = args
            return rec
        except Exception as e:  # noqa: BLE001 — 单个工具失败不应中断整体抓取
            return {"isError": True, "text": f"{type(e).__name__}: {e}", "json": None,
                    "_args": args, "_exception": True}


# ============================================================================
# 落盘辅助
# ============================================================================
def write_raw(raw_dir: Path, name: str, rec: dict) -> None:
    """把单个工具响应写成独立文件（name 可含子目录），便于人工检查。"""
    if rec.get("json") is not None:
        target = raw_dir / f"{name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(rec["json"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        # 非 JSON（如 getMeta 的 markdown）原样保存
        ext = "md" if name.endswith("getMeta") or "Meta" in name else "txt"
        target = raw_dir / f"{name}.{ext}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rec.get("text", ""), encoding="utf-8")


def status_str(rec: dict) -> str:
    if rec.get("_missing"):
        return "MISSING"
    if rec.get("isError"):
        return "ERROR"
    return "ok"


# ============================================================================
# 主流程
# ============================================================================
async def run_capture(cfg: dict) -> int:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    raw_dir: Path = cfg["rawDir"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        print(msg, flush=True)

    # 基础 id 参数（各工具会按自身 schema 过滤）
    id_args = {
        "fileId": cfg["fileId"],
        "layerId": cfg["layerId"],
        "sourceLayerId": cfg["sourceLayerId"],
        "shortLink": cfg["shortLink"],
        "format": "json",
    }

    # 组装 npx 命令
    npx = shutil.which("npx") or ("npx.cmd" if sys.platform == "win32" else "npx")
    server_args = ["-y", cfg["mcpPackage"], f"--token={cfg['token']}", f"--url={cfg['apiBaseUrl']}"]
    child_env = os.environ.copy()
    child_env["MG_MCP_TOKEN"] = cfg["token"]          # 兼容以 env 读取 token 的版本
    child_env.setdefault("API_BASE_URL", cfg["apiBaseUrl"])

    server = StdioServerParameters(command=npx, args=server_args, env=child_env)

    manifest = {
        "capturedAt": datetime.now(timezone.utc).astimezone().isoformat(),
        "projectName": cfg["projectName"],
        "mcpPackage": cfg["mcpPackage"],
        "apiBaseUrl": cfg["apiBaseUrl"],
        "fileId": cfg["fileId"],
        "layerId": cfg["layerId"],
        "sourceLayerId": cfg["sourceLayerId"],
        "shortLink": cfg["shortLink"],
        "toolInventory": [],
        "steps": [],
        "totalSections": 0,
        "componentDocumentLinks": [],
        "unresolved": [],
    }
    responses: dict[str, Any] = {}

    def record_step(step: str, tool: str, rec: dict, extra: dict | None = None) -> None:
        entry = {"step": step, "tool": tool, "status": status_str(rec), "args": rec.get("_args", {})}
        if extra:
            entry.update(extra)
        manifest["steps"].append(entry)
        log(f"  [{step}] {tool:<20} -> {entry['status']}")

    log(f"启动 MCP 服务器: {npx} {' '.join(a if not a.startswith('--token') else '--token=***' for a in server_args)}")
    log(f"设计文件: fileId={cfg['fileId'] or '(短链)'} layerId={cfg['layerId'] or '(短链)'}")

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ---- 工具清单发现 ----
            tools_result = await session.list_tools()
            tool_index: dict[str, str] = {}
            allowed_props: dict[str, set[str]] = {}
            for t in tools_result.tools:
                tool_index[CANON(t.name)] = t.name
                schema = getattr(t, "inputSchema", None) or {}
                props = set((schema.get("properties") or {}).keys()) if isinstance(schema, dict) else set()
                allowed_props[t.name] = props
                manifest["toolInventory"].append(
                    {"name": t.name, "inputProps": sorted(props)}
                )
            log(f"发现 {len(tool_index)} 个工具: {', '.join(sorted(tool_index))}")

            runner = McpRunner(session, tool_index, log)

            # ================= Step 1: getDsl（必须最先） =================
            log("Step 1: getDsl")
            dsl = await runner.call("getDsl", id_args, allowed_props=allowed_props, timeout=180)
            responses["getDsl"] = dsl
            write_raw(raw_dir, "01-getDsl/getDsl", dsl)
            component_links = extract_component_links(dsl.get("json"))
            manifest["componentDocumentLinks"] = component_links
            record_step("1", "getDsl", dsl, {"componentLinks": len(component_links)})

            # ================= Step 2: getMeta =================
            log("Step 2: getMeta")
            if cfg["fileId"] and cfg["layerId"]:
                meta = await runner.call("getMeta", id_args, allowed_props=allowed_props)
                responses["getMeta"] = meta
                write_raw(raw_dir, "02-getMeta/getMeta", meta)
                record_step("2", "getMeta", meta)
            else:
                manifest["unresolved"].append({"tool": "getMeta", "reason": "需要显式 fileId+layerId（仅短链无法调用）"})
                log("  [2] getMeta            -> SKIP（缺 fileId/layerId）")

            # ================= Step 3: getDesignSections（概览） =================
            log("Step 3: getDesignSections (overview)")
            overview = await runner.call("getDesignSections", id_args, allowed_props=allowed_props, timeout=180)
            responses["getDesignSections_overview"] = overview
            write_raw(raw_dir, "03-getDesignSections/overview", overview)
            total_sections = extract_total_sections(overview.get("json"))
            total_sections = min(total_sections, 200)  # 安全上限
            manifest["totalSections"] = total_sections
            record_step("3", "getDesignSections", overview, {"totalSections": total_sections})

            # ================= Step 4: getDesignSections（逐段，分批并发） =================
            log(f"Step 4: getDesignSections (sections 0..{total_sections - 1}, batch={cfg['sectionBatchSize']})")
            section_records: list[dict] = []
            batch = cfg["sectionBatchSize"]
            for start in range(0, total_sections, batch):
                idxs = list(range(start, min(start + batch, total_sections)))
                coros = [
                    runner.call(
                        "getDesignSections",
                        {**id_args, "sectionIndex": i},
                        allowed_props=allowed_props,
                        timeout=180,
                    )
                    for i in idxs
                ]
                results = await asyncio.gather(*coros)
                for i, rec in zip(idxs, results):
                    rec["sectionIndex"] = i
                    section_records.append(rec)
                    write_raw(raw_dir, f"03-getDesignSections/section-{i:02d}", rec)
                    record_step(f"4.{i}", "getDesignSections", rec, {"sectionIndex": i})
            responses["getDesignSections_sections"] = section_records

            # ================= Step 5: svgs / texts / extractSvg（并发补全） =================
            log("Step 5: getDesignSvgs + getDesignTexts + extractSvg")
            svgs, texts, extracted = await asyncio.gather(
                runner.call("getDesignSvgs", id_args, allowed_props=allowed_props, timeout=180),
                runner.call("getDesignTexts", id_args, allowed_props=allowed_props, timeout=180),
                runner.call("extractSvg", id_args, allowed_props=allowed_props, timeout=180),
            )
            responses["getDesignSvgs"] = svgs
            responses["getDesignTexts"] = texts
            responses["extractSvg"] = extracted
            write_raw(raw_dir, "05-getDesignSvgs/getDesignSvgs", svgs)
            write_raw(raw_dir, "05-getDesignTexts/getDesignTexts", texts)
            write_raw(raw_dir, "05-extractSvg/extractSvg", extracted)
            record_step("5a", "getDesignSvgs", svgs)
            record_step("5b", "getDesignTexts", texts)
            record_step("5c", "extractSvg", extracted)

            # ================= Step 6: getComponentLink（条件触发） =================
            log(f"Step 6: getComponentLink ({len(component_links)} links)")
            comp_docs: list[dict] = []
            for i, url in enumerate(component_links):
                rec = await runner.call("getComponentLink", {"url": url}, allowed_props=allowed_props)
                rec["url"] = url
                comp_docs.append(rec)
                write_raw(raw_dir, f"06-getComponentLink/link-{i:02d}", rec)
                record_step(f"6.{i}", "getComponentLink", rec, {"url": url})
            responses["getComponentLink"] = comp_docs
            if not component_links:
                log("  [6] getComponentLink   -> SKIP（无组件文档链接）")

            # ================= Step 7: getD2c（条件触发） =================
            log("Step 7: getD2c")
            if cfg["fileId"] and cfg["layerId"]:
                content_id = f"{cfg['fileId']}-{cfg['layerId'].replace(':', '-')}"
                d2c_out = str(raw_dir / "07-getD2c" / "d2c-out")
                d2c = await runner.call(
                    "getD2c",
                    {"contentId": content_id, "documentId": cfg["fileId"], "outDir": d2c_out},
                    allowed_props=allowed_props,
                    timeout=180,
                )
                responses["getD2c"] = d2c
                write_raw(raw_dir, "07-getD2c/getD2c", d2c)
                text = d2c.get("text", "") or ""
                # 用返回信封的 code 判定，而不是在 HTML/CSS 正文里做子串匹配
                # （MasterGo 约定 code="00000" 为成功；404 / code 10009 表示该节点无 D2C 产物）
                dj = d2c.get("json")
                d2c_code = dj.get("code") if isinstance(dj, dict) else None
                d2c_status = dj.get("status") if isinstance(dj, dict) else None
                success_codes = {"00000", "0", 0}
                is_ok = (not d2c.get("isError")) and (
                    d2c_code in success_codes if d2c_code is not None else True
                )
                if not is_ok:
                    reason = f"D2C 返回异常 code={d2c_code} status={d2c_status}（404/code 10009 表示该节点无 D2C 产物），已跳过"
                    manifest["unresolved"].append(
                        {"tool": "getD2c", "contentId": content_id, "code": d2c_code, "reason": reason}
                    )
                    record_step("7", "getD2c", d2c, {"contentId": content_id, "note": "unresolved", "code": d2c_code})
                else:
                    record_step("7", "getD2c", d2c, {"contentId": content_id, "code": d2c_code})
            else:
                manifest["unresolved"].append({"tool": "getD2c", "reason": "需要显式 fileId+layerId"})
                log("  [7] getD2c             -> SKIP（缺 fileId/layerId）")

    # ---- 汇总落盘 ----
    combined = {"captureManifest": manifest, "responses": responses}
    combined_path = raw_dir / "mastergo-mcp-raw.json"
    combined_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    (raw_dir / "_capture-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- 结果概览 ----
    ok = sum(1 for s in manifest["steps"] if s["status"] == "ok")
    err = sum(1 for s in manifest["steps"] if s["status"] in ("ERROR", "MISSING"))
    print("\n================= 抓取完成 =================")
    print(f"工具调用: {ok} 成功 / {err} 失败或缺失")
    print(f"totalSections: {manifest['totalSections']}")
    print(f"组件文档链接: {len(manifest['componentDocumentLinks'])}")
    print(f"unresolved: {len(manifest['unresolved'])}")
    print(f"合并数据: {combined_path}")
    print(f"原始分文件目录: {raw_dir}")
    if manifest["unresolved"]:
        print("未解决项:")
        for u in manifest["unresolved"]:
            print(f"  - {u.get('tool')}: {u.get('reason')}")
    return 0 if err == 0 else 1


# ============================================================================
# CLI
# ============================================================================
def do_check(cfg: dict) -> int:
    print("=== --check 配置校验 ===")
    print(f"SKILL_ROOT      : {SKILL_ROOT}")
    print(f"projectName     : {cfg['projectName']}")
    print(f"designUrl       : {cfg['designUrl'] or '(未设置)'}")
    print(f"fileId          : {cfg['fileId'] or '(空)'}")
    print(f"layerId         : {cfg['layerId'] or '(空)'}")
    print(f"sourceLayerId   : {cfg['sourceLayerId'] or '(空)'}")
    print(f"shortLink       : {cfg['shortLink'] or '(无)'}")
    print(f"apiBaseUrl      : {cfg['apiBaseUrl']}")
    print(f"mcpPackage      : {cfg['mcpPackage']}")
    print(f"token           : {'已配置' if cfg['token'] else '缺失'}")
    print(f"rawDir          : {cfg['rawDir']}")

    try:
        import mcp  # noqa: F401
        from mcp import ClientSession, StdioServerParameters  # noqa: F401
        from mcp.client.stdio import stdio_client  # noqa: F401
        print("mcp SDK         : 已安装")
    except Exception as e:  # noqa: BLE001
        print(f"mcp SDK         : 未安装（pip install mcp） -> {e}")

    npx = shutil.which("npx") or ("npx.cmd" if sys.platform == "win32" else "npx")
    print(f"npx             : {npx if shutil.which(npx) else '未找到，请安装 Node.js'}")

    errs = validate_config(cfg)
    if errs:
        print("\n发现问题:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("\n配置校验通过，可执行完整抓取。")
    return 0


def _force_utf8() -> None:
    """Windows 控制台默认 GBK，中文输出到 UTF-8 终端会乱码，这里统一为 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _force_utf8()
    ap = argparse.ArgumentParser(description="MasterGo MCP 原始数据抓取脚本")
    ap.add_argument("--check", action="store_true", help="只校验配置/依赖/URL 解析，不联网")
    ap.add_argument("--design-url", default="", help="覆盖 designUrl")
    ap.add_argument("--file-id", default="", help="覆盖 fileId")
    ap.add_argument("--layer-id", default="", help="覆盖 layerId(rootNodeId)")
    ap.add_argument("--token", default="", help="覆盖 MasterGo token")
    ap.add_argument("--url", default="", help="覆盖 apiBaseUrl")
    ap.add_argument("--section-batch", type=int, default=0, help="section 并发批大小（默认 4）")
    args = ap.parse_args()

    cfg = resolve_config(args)

    if args.check:
        return do_check(cfg)

    errs = validate_config(cfg)
    fatal = [e for e in errs if "将被跳过" not in e and "建议用完整链接" not in e]
    if fatal:
        print("配置错误，无法开始抓取：", file=sys.stderr)
        for e in fatal:
            print(f"  - {e}", file=sys.stderr)
        print("\n先运行 `python fetch_mcp_data.py --check` 检查配置。", file=sys.stderr)
        return 2

    try:
        return asyncio.run(run_capture(cfg))
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
