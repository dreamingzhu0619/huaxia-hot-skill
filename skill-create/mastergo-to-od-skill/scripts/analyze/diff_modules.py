#!/usr/bin/env python3
"""
diff_modules.py -- 同类模块合并 + 逐属性 diff invariant/variable。

Step 4 of the new pipeline:
  1. Compute skeleton signature for each module (node type hierarchy only).
  2. Group modules with identical signatures as merge candidates.
  3. For merge groups (>=2 instances): per-attribute diff at matched tree positions.
  4. For singletons: auto-classify unconditional fixed, list remaining TEXT for review.
  5. Chart detection: >=5 PATH/LAYER children + sibling "数据来源" TEXT signal.

Output:
  data/analysis/merge_groups.json   -- component groups + singletons
  data/analysis/diff_result.json    -- per-node per-attribute invariant/variable
  data/analysis/singleton_texts.json -- TEXT nodes needing manual review

Usage:
  python scripts/analyze/diff_modules.py
  python scripts/analyze/diff_modules.py --output-dir <path>
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = None  # set after arg parsing: SKILL_ROOT / "data" / args.project
MODULES_DIR = None
ANALYSIS_DIR = None

# Compliance keywords that auto-mark TEXT as fixed
COMPLIANCE_KEYWORDS = [
    "风险", "投资须谨慎", "基金合同", "不保证", "谨慎", "损失",
    "基金非存款", "投资有风险", "理财非存款", "产品有风险",
    "过往业绩", "不预示", "不构成", "保证收益",
]

# Fee table headers that auto-mark TEXT as fixed
FEE_HEADER_KEYWORDS = [
    "管理费", "托管费", "赎回费", "销售服务费", "申购费",
    "认购费", "转换费", "手续费", "费率", "费用",
]

# Chart detection: sibling TEXT containing these phrases
CHART_SOURCE_KEYWORDS = [
    "数据来源", "资料来源", "Wind", "wind", "数据来源：",
    "资料来源：", "统计区间", "数据截止",
]

# Chart detection: node name containing these phrases
CHART_NAME_KEYWORDS = ["图表", "统计", "图示", "走势", "趋势"]


def skeleton_signature(node):
    """Recursively build type-only skeleton string.
    Format: TYPE or TYPE>[child1,child2,...]
    Only looks at type hierarchy, ignores coordinates and text content.
    """
    children = node.get("children") or []
    if not children:
        return node.get("type", "UNKNOWN")

    child_sigs = []
    for child in children:
        child_sigs.append(skeleton_signature(child))

    inner = ",".join(child_sigs)
    return f"{node.get('type', 'UNKNOWN')}>[{inner}]"


def collect_text_nodes(node, path=""):
    """Recursively collect all TEXT nodes with their tree path."""
    texts = []
    current_path = f"{path}/{node.get('name', '')}" if path else node.get("name", "")
    node_type = node.get("type", "")

    if node_type == "TEXT":
        texts.append({
            "id": node.get("id"),
            "name": node.get("name"),
            "text": node.get("text", ""),
            "path": current_path,
        })

    for i, child in enumerate(node.get("children") or []):
        texts.extend(collect_text_nodes(child, f"{current_path}[{i}]"))

    return texts


def get_node_at_path(node, path_indices):
    """Follow a list of child indices to get a node at a specific tree position."""
    current = node
    for idx in path_indices:
        children = current.get("children") or []
        if idx >= len(children):
            return None
        current = children[idx]
    return current


def build_path_index(node, prefix=()):
    """Build a map of (depth_childIndex, ..., childIndex) -> nodeId for tree-position matching."""
    index = {}
    node_type = node.get("type", "")
    node_id = node.get("id", "")

    if prefix:
        index[prefix] = {"id": node_id, "type": node_type}

    for i, child in enumerate(node.get("children") or []):
        child_prefix = prefix + (i,)
        index.update(build_path_index(child, child_prefix))

    return index


def diff_node_attributes(nodes_at_path):
    """Compare attributes across instances. Returns per-attribute status.

    Args:
        nodes_at_path: list of node dicts from different instances at the same tree position.

    Returns:
        dict: {attribute_name: {status: "invariant"|"variable", value/common_value, values[...]}}
    """
    if not nodes_at_path:
        return {}

    first = nodes_at_path[0]
    result = {}
    node_type = first.get("type", "")

    # Helper: compare a value across all instances
    def compare_attr(key, get_value_fn, is_numeric=False):
        values = []
        for n in nodes_at_path:
            if n is None:
                values.append(None)
            else:
                values.append(get_value_fn(n))

        # Check if all same
        first_val = values[0]
        all_same = True
        for v in values[1:]:
            if is_numeric:
                if not _nums_equal(v, first_val):
                    all_same = False
                    break
            else:
                if v != first_val:
                    all_same = False
                    break

        if all_same:
            return {"status": "invariant", "value": first_val}
        else:
            return {"status": "variable", "values": values}

    # TEXT node attributes
    if node_type == "TEXT":
        # text content
        result["text"] = compare_attr("text", lambda n: n.get("text", ""))

        # font properties from textRuns
        runs = first.get("textRuns") or []
        if runs:
            font = runs[0].get("font") or {}

            result["font.family"] = compare_attr(
                "font.family",
                lambda n: ((n.get("textRuns") or [{}])[0].get("font") or {}).get("family")
            )
            result["font.size"] = compare_attr(
                "font.size",
                lambda n: ((n.get("textRuns") or [{}])[0].get("font") or {}).get("size"),
                is_numeric=True
            )
            result["font.lineHeight"] = compare_attr(
                "font.lineHeight",
                lambda n: ((n.get("textRuns") or [{}])[0].get("font") or {}).get("lineHeight")
            )
            result["font.letterSpacing"] = compare_attr(
                "font.letterSpacing",
                lambda n: ((n.get("textRuns") or [{}])[0].get("font") or {}).get("letterSpacing")
            )
            result["font.weight"] = compare_attr(
                "font.weight",
                lambda n: ((n.get("textRuns") or [{}])[0].get("font") or {}).get("style")
            )
            result["font.decoration"] = compare_attr(
                "font.decoration",
                lambda n: ((n.get("textRuns") or [{}])[0].get("font") or {}).get("decoration")
            )
            result["font.case"] = compare_attr(
                "font.case",
                lambda n: ((n.get("textRuns") or [{}])[0].get("font") or {}).get("case")
            )

            # text color
            result["color"] = compare_attr(
                "color",
                lambda n: ((n.get("textRuns") or [{}])[0]).get("color") if (n.get("textRuns") or []) else None
            )

        # text alignment
        result["textAlign"] = compare_attr("textAlign", lambda n: n.get("textAlign"))

    # Layout dimensions (all node types)
    result["layoutStyle.width"] = compare_attr(
        "layoutStyle.width",
        lambda n: (n.get("layoutStyle") or {}).get("width"),
        is_numeric=True
    )
    result["layoutStyle.height"] = compare_attr(
        "layoutStyle.height",
        lambda n: (n.get("layoutStyle") or {}).get("height"),
        is_numeric=True
    )

    # Visual properties for non-TEXT nodes
    if node_type in ("LAYER", "FRAME", "GROUP", "PATH"):
        result["fill"] = compare_attr("fill", lambda n: n.get("fill"))
        result["borderRadius"] = compare_attr("borderRadius", lambda n: n.get("borderRadius"))
        result["strokeColor"] = compare_attr("strokeColor", lambda n: n.get("strokeColor"))
        result["strokeWidth"] = compare_attr("strokeWidth", lambda n: n.get("strokeWidth"))
        result["strokeAlign"] = compare_attr("strokeAlign", lambda n: n.get("strokeAlign"))
        result["opacity"] = compare_attr("opacity", lambda n: n.get("opacity"), is_numeric=True)
        result["effect"] = compare_attr("effect", lambda n: _effect_key(n.get("effect")))

    return result


def _nums_equal(a, b, tolerance=0.01):
    """Compare two numbers with tolerance."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < tolerance
    except (TypeError, ValueError):
        return a == b


def _effect_key(effect):
    """Convert effect dict to a hashable key for comparison."""
    if not effect:
        return None
    return json.dumps(effect, sort_keys=True, default=str)


def detect_chart_group(node, sibling_texts):
    """Detect if a GROUP node is a chart container.

    Signals (from REDESIGN.md Section 3.1):
    - GROUP has >=5 PATH/LAYER child nodes (complex graphics)
    - Sibling TEXT contains "数据来源"/"资料来源" etc.
    - Node name contains "图表"/"统计"/"图示"
    - Previous sibling is a title-like TEXT
    """
    node_type = node.get("type", "")
    if node_type != "GROUP":
        return False

    children = node.get("children") or []
    path_layer_count = sum(
        1 for c in children if c.get("type") in ("PATH", "LAYER")
    )

    # Signal 1: Complex graphics
    if path_layer_count < 5:
        # Also check total descendant count of PATH/LAYER
        def count_path_layer(n):
            count = 1 if n.get("type") in ("PATH", "LAYER") else 0
            for c in n.get("children") or []:
                count += count_path_layer(c)
            return count

        path_layer_count = count_path_layer(node)

    if path_layer_count < 5:
        return False

    # Signal 2: Sibling data source text
    for st in sibling_texts:
        for kw in CHART_SOURCE_KEYWORDS:
            if kw in (st.get("text") or ""):
                return True

    # Signal 3: Name contains chart keywords
    name = node.get("name", "")
    for kw in CHART_NAME_KEYWORDS:
        if kw in name:
            return True

    return False


def auto_classify_singleton_text(text_node):
    """Auto-classify a TEXT node in a singleton module as fixed.

    Rules:
    - Type is not TEXT (handled by caller)
    - Contains compliance keywords
    - Contains fee table header keywords
    """
    text = text_node.get("text") or ""
    name = text_node.get("name") or ""

    for kw in COMPLIANCE_KEYWORDS:
        if kw in text or kw in name:
            return "fixed"

    for kw in FEE_HEADER_KEYWORDS:
        if kw in text or kw in name:
            return "fixed"

    return "needs_review"


def build_node_path_map(node, prefix=()):
    """Build map of tree_position -> node for all nodes in a tree."""
    result = {}

    node_type = node.get("type", "")
    if prefix:  # Skip root
        result[prefix] = node

    for i, child in enumerate(node.get("children") or []):
        child_prefix = prefix + (i,)
        result.update(build_node_path_map(child, child_prefix))

    return result


def diff_group(group_modules):
    """Diff a merge group (2+ instances with identical skeleton).

    Returns full per-node per-attribute diff result.
    """
    # Build path maps for all instances
    path_maps = []
    for mod in group_modules:
        node = mod.get("node")
        if node:
            path_maps.append(build_node_path_map(node))

    if not path_maps:
        return {}

    # Union of all paths
    all_paths = set()
    for pm in path_maps:
        all_paths.update(pm.keys())

    result = {"nodes": {}, "chartGroups": []}

    for path in sorted(all_paths, key=lambda p: (len(p), p)):
        nodes_at_path = []
        for pm in path_maps:
            nodes_at_path.append(pm.get(path))

        if not any(nodes_at_path):
            continue

        first_node = next((n for n in nodes_at_path if n is not None), None)
        if first_node is None:
            continue

        node_id = first_node.get("id", "")
        node_type = first_node.get("type", "")
        node_name = first_node.get("name", "")

        diff = diff_node_attributes(nodes_at_path)
        result["nodes"][str(path)] = {
            "id": node_id,
            "type": node_type,
            "name": node_name,
            "attributes": diff,
        }

        # Check if GROUP internal structure differs -> mark as variable structure
        if node_type == "GROUP":
            child_counts = []
            for pm in path_maps:
                n = pm.get(path)
                if n:
                    child_counts.append(len(n.get("children") or []))
                else:
                    child_counts.append(0)

            if len(set(child_counts)) > 1:
                result["nodes"][str(path)]["internalStructure"] = {
                    "status": "variable",
                    "childCounts": child_counts,
                    "reason": "child count differs across instances",
                }

    # Chart detection: iterate through all GROUP nodes
    for path_str, node_diff in result["nodes"].items():
        if node_diff.get("type") != "GROUP":
            continue

        # Get sibling TEXT nodes from the first instance
        path = tuple(int(x) for x in path_str.strip("()").split(",")) if path_str.strip("()") else ()
        parent_path = path[:-1] if len(path) > 0 else ()

        sibling_texts = []
        for p, nd in result["nodes"].items():
            p_tuple = tuple(int(x) for x in p.strip("()").split(",")) if p.strip("()") else ()
            if len(p_tuple) == len(path) and p_tuple[:-1] == parent_path and p != path_str:
                if nd.get("type") == "TEXT":
                    sibling_texts.append(nd)

        first_instance_node = path_maps[0].get(path) if path_maps else None
        if first_instance_node and detect_chart_group(first_instance_node, sibling_texts):
            result["chartGroups"].append({
                "path": path_str,
                "nodeId": node_diff["id"],
                "name": node_diff["name"],
            })
            # Mark as chart container - entire GROUP becomes {{slot}}
            node_diff["classification"] = "chart_container"

    return result


def run(output_dir=None):
    """Main: load modules, compare, output analysis."""
    out_dir = Path(output_dir) if output_dir else ANALYSIS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load index
    index_path = MODULES_DIR / "_index.json"
    if not index_path.exists():
        print(f"ERROR: _index.json not found at {index_path}")
        print("Run split_modules.py first.")
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    modules_meta = index.get("modules", [])
    design_scale = index.get("meta", {}).get("designScale", {"scale": 3, "logicalWidth": 375})

    # Load all modules
    modules = {}
    for m in modules_meta:
        file_name = m.get("fileName")
        if not file_name:
            continue
        mod_path = MODULES_DIR / file_name
        if mod_path.exists():
            with open(mod_path, "r", encoding="utf-8") as f:
                modules[file_name] = json.load(f)

    print(f"Loaded {len(modules)} modules")

    # Step 1: Compute skeleton signatures
    signatures = {}
    for file_name, mod in modules.items():
        node = mod.get("node")
        if node:
            sig = skeleton_signature(node)
            signatures[file_name] = sig

    # Step 2: Group by signature
    sig_groups = defaultdict(list)
    for file_name, sig in signatures.items():
        sig_groups[sig].append(file_name)

    # Step 3: Build merge groups
    merge_groups = []
    singletons = []

    for sig, file_names in sig_groups.items():
        if len(file_names) >= 2:
            # Multiple modules with same skeleton -> merge candidate
            member_modules = []
            for fn in file_names:
                mod = modules[fn]
                member_modules.append(mod["meta"]["moduleName"])

            # Pick first as representative
            rep_module = modules[file_names[0]]
            rep_name = rep_module["meta"]["moduleName"]

            # Generate component name from first module's slug
            slug = rep_module["meta"]["slug"]
            # Strip trailing A/B/C for merged groups
            import re
            component_name = re.sub(r"[A-C]$", "", slug)

            merge_groups.append({
                "componentName": component_name,
                "memberModules": member_modules,
                "representativeModule": file_names[0],
                "instanceCount": len(file_names),
                "skeletonSignature": sig,
                "mergeMethod": "skeleton_match",
            })
        else:
            # Singleton
            fn = file_names[0]
            mod = modules[fn]
            singletons.append({
                "componentName": mod["meta"]["slug"],
                "module": mod["meta"]["moduleName"],
                "fileName": fn,
                "instanceCount": 1,
                "skeletonSignature": sig,
                "requiresManualClassification": True,
            })

    print(f"\nMerge groups: {len(merge_groups)}")
    for g in merge_groups:
        print(f"  {g['componentName']}: {g['memberModules']} ({g['instanceCount']} instances)")

    print(f"\nSingletons: {len(singletons)}")
    for s in singletons:
        print(f"  {s['componentName']}: {s['module']}")

    # Step 4: Diff merge groups
    diff_results = {}
    for group in merge_groups:
        group_modules = [modules[fn] for fn in group["representativeModule"]]
        # Actually get ALL member modules for diff
        member_fns = []
        for member_name in group["memberModules"]:
            for fn, mod in modules.items():
                if mod["meta"]["moduleName"] == member_name:
                    member_fns.append(fn)
                    break

        group_modules = [modules[fn] for fn in member_fns if fn in modules]
        if len(group_modules) >= 2:
            diff = diff_group(group_modules)
            diff["componentName"] = group["componentName"]
            diff["instanceCount"] = len(group_modules)
            diff_results[group["componentName"]] = diff

    # Step 5: Auto-classify singleton TEXT nodes
    singleton_texts = {}
    for s in singletons:
        fn = s["fileName"]
        mod = modules.get(fn)
        if not mod:
            continue

        node = mod.get("node")
        if not node:
            continue

        texts = collect_text_nodes(node)
        classified = []

        for t in texts:
            classification = auto_classify_singleton_text(t)
            if t["text"]:
                classified.append({
                    "id": t["id"],
                    "name": t["name"],
                    "text": t["text"],
                    "path": t["path"],
                    "classification": classification,
                })

        auto_fixed = [c for c in classified if c["classification"] == "fixed"]
        needs_review = [c for c in classified if c["classification"] == "needs_review"]

        singleton_texts[s["componentName"]] = {
            "moduleName": s["module"],
            "autoFixed": auto_fixed,
            "needsReview": needs_review,
        }

        print(f"\n  {s['componentName']}: {len(auto_fixed)} auto-fixed, {len(needs_review)} need review")
        for t in needs_review:
            print(f"    ? {t['id']} \"{t['name']}\": \"{t['text'][:60]}\"")

    # Write output
    merge_output = {
        "groups": merge_groups,
        "singletons": singletons,
        "designScale": design_scale,
    }

    with open(out_dir / "merge_groups.json", "w", encoding="utf-8") as f:
        json.dump(merge_output, f, ensure_ascii=False, indent=2)

    with open(out_dir / "diff_result.json", "w", encoding="utf-8") as f:
        json.dump(diff_results, f, ensure_ascii=False, indent=2)

    with open(out_dir / "singleton_texts.json", "w", encoding="utf-8") as f:
        json.dump(singleton_texts, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis written to {out_dir}/")
    print(f"  merge_groups.json   - component groups + singletons")
    print(f"  diff_result.json    - per-attribute diff for merged groups")
    print(f"  singleton_texts.json - TEXT nodes needing manual review")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diff modules for invariant/variable classification")
    parser.add_argument("--project", required=True, help="Project name (e.g. huaxia-hot-citc)")
    parser.add_argument("--output-dir", help="Output directory (default: data/<project>/analysis/)")
    args = parser.parse_args()

    PROJECT_DIR = SKILL_ROOT / "data" / args.project
    MODULES_DIR = PROJECT_DIR / "modules"
    ANALYSIS_DIR = Path(args.output_dir) if args.output_dir else PROJECT_DIR / "analysis"
    run(output_dir=str(ANALYSIS_DIR))
