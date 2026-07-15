#!/usr/bin/env python3
"""
generate_module_css.py —— 读 data/modules/*.json，为每个模块生成一份 .css。

只负责「生成」：把每个节点用 css_core 转成 CSS 规则，写到
assets/styles/modules/{同名}.css。漏没漏由人肉眼对照真实设计稿判断，本脚本不做任何判断。

规则：
  - 选择器：模块根 = .m-{序号}-{slug}；其余节点 = .n-{id 冒号转横线}。
  - 每条规则前带一行定位注释（id / 名称 / 类型，图片附 url、SVG/PATH/mask 附标记），纯为可读。
  - z-index 按兄弟顺序注入；mix-blend-mode/overflow/object-fit 来自 d2cCss。

用法：
  python scripts/render/generate_module_css.py            # 全量生成
  python scripts/render/generate_module_css.py --dry-run  # 只打印概要，不写文件
  python scripts/render/generate_module_css.py --check    # 只校验输入
  python scripts/render/generate_module_css.py --module 0 # 只生成某个模块
"""

import sys
import json
import argparse
from pathlib import Path

# --- Windows 编码适配 ---
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_DIR = PROJECT_ROOT / "data" / "modules"
OUT_DIR = PROJECT_ROOT / "assets" / "styles" / "modules"
LIB_DIR = PROJECT_ROOT / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR))
import css_core  # noqa: E402


# ============================================================================
# 工具
# ============================================================================

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def module_files() -> list[Path]:
    """data/modules 下的模块 JSON（排除 _index.json），按文件名排序。"""
    return sorted(p for p in MODULES_DIR.glob("*.json") if not p.name.startswith("_"))


def _ordered_items(css: dict) -> list[tuple[str, str]]:
    idx = {p: i for i, p in enumerate(css_core.PROP_ORDER)}
    return sorted(css.items(), key=lambda kv: (idx.get(kv[0], len(idx)), kv[0]))


def _node_comment(node: dict) -> str:
    """节点定位注释：id 名称 [类型] + 资源标记（纯可读，不做判断）。"""
    nid = node.get("id", "")
    name = (node.get("name") or "").strip()
    ntype = node.get("type", "")
    extra = ""
    fill = node.get("fill")
    if isinstance(fill, dict) and fill.get("url"):
        extra = f"  img={fill['url']}"
    elif node.get("hasSvg"):
        extra = f"  svg=assets.svgs[{nid}]"
    elif ntype == "PATH":
        extra = "  PATH→内联SVG"
    if node.get("mask"):
        extra += f"  mask={node['mask']}"
    return f"/* {nid} {name} [{ntype}]{extra} */"


def _format_rule(selector: str, node: dict, css: dict) -> str:
    lines = [_node_comment(node), f"{selector} {{"]
    for prop, val in _ordered_items(css):
        if val is not None:
            lines.append(f"  {prop}: {val};")
    lines.append("}")
    return "\n".join(lines)


# ============================================================================
# 遍历一个模块 -> CSS 文本
# ============================================================================

def render_module(module: dict) -> tuple[str, int]:
    """返回 (css_text, rule_count)。"""
    meta = module.get("meta", {})
    root = module.get("node", {})
    idx = meta.get("moduleIndex", 0)
    slug = meta.get("slug", "module")
    module_class = f"m-{idx:02d}-{slug}"

    rules: list[str] = []

    def walk(node, *, is_root, z_index):
        selector = f".{module_class}" if is_root else f".{css_core.css_class(node['id'])}"
        css = css_core.node_css_full(node, is_root=is_root, z_index=z_index)
        rules.append(_format_rule(selector, node, css))
        for i, child in enumerate(node.get("children", [])):
            walk(child, is_root=False, z_index=i)

    walk(root, is_root=True, z_index=None)

    header = (
        f"/* {meta.get('fileName', '')}  {meta.get('moduleName', '')}\n"
        f"   由 getDsl 生成；mix-blend-mode/overflow/object-fit 取自 d2cCss。\n"
        f"   根 .{module_class}，其余节点 .n-{{id}}。共 {len(rules)} 条规则。 */\n"
    )
    return header + "\n\n".join(rules) + "\n", len(rules)


# ============================================================================
# 主流程
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="从模块 JSON 生成每模块 .css")
    parser.add_argument("--check", action="store_true", help="只校验输入")
    parser.add_argument("--dry-run", action="store_true", help="只打印概要，不写文件")
    parser.add_argument("--module", type=int, default=None, help="只生成指定 moduleIndex")
    args = parser.parse_args()

    print("=" * 60)
    print("generate_module_css —— 模块 JSON -> 每模块 .css")
    print("=" * 60)

    files = module_files()
    print(f"\n[1/3] 校验输入... 发现 {len(files)} 个模块 JSON  (源: {MODULES_DIR})")
    if not files:
        print("\n  [ERR] data/modules 下没有模块 JSON。先跑 split_modules.py。", file=sys.stderr)
        sys.exit(1)
    if args.check:
        for p in files:
            print(f"  [OK] {p.name}")
        print("\n  [DONE] --check 完成。")
        return

    print("\n[2/3] 生成 CSS...")
    outputs: list[tuple[str, str, int]] = []  # (out_name, css_text, rule_count)
    for p in files:
        module = load_json(p)
        idx = module.get("meta", {}).get("moduleIndex")
        if args.module is not None and idx != args.module:
            continue
        css_text, count = render_module(module)
        out_name = p.stem + ".css"
        outputs.append((out_name, css_text, count))
        print(f"  [{idx:02d}] {out_name:<30} {count:>3} 条规则")

    if not outputs:
        print(f"\n  [WARN] --module {args.module} 没匹配到任何模块。")
        return

    total = sum(c for _, _, c in outputs)
    print(f"\n  合计 {len(outputs)} 个模块 / {total} 条规则")

    if args.dry_run:
        print("\n  [DONE] --dry-run：未写文件。")
        return

    print("\n[3/3] 写入...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for out_name, css_text, _ in outputs:
        out_path = OUT_DIR / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(css_text)
        print(f"  {out_path.relative_to(PROJECT_ROOT)}  ({out_path.stat().st_size / 1024:.1f} KB)")

    print("\n" + "=" * 60)
    print(f"[DONE] 生成完成 -> {OUT_DIR.relative_to(PROJECT_ROOT)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
