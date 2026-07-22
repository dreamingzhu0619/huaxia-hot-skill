"""
Step 2 - Phase 1 构建脚本：根据 frameType 走不同分支，生成 step2-04_slots-definition.json。

- fully-fixed → 直接输出 fullyFixed: true
- template    → 读 step2-02_text-judgments.json，输出 fixedGroups + slots（平铺，无 zone）
- content     → 纯几何分析，输出 zones + slots

Usage:
  python scripts/step2_build_slots.py --project huaxia-hot-citc
"""

import json
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 几何工具
# ---------------------------------------------------------------------------

VISUAL_TYPES = {"LAYER", "PATH", "VECTOR", "RECTANGLE", "ELLIPSE", "SVG_ELLIPSE"}
CONTAINER_TYPES = {"GROUP", "FRAME", "COMPONENT", "INSTANCE"}

# 内容区统一内边距（px），所有项目通用
CONTENT_PADDING = 24


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    def overlaps(self, other: "Rect") -> bool:
        return (
            self.x < other.right
            and self.right > other.x
            and self.y < other.bottom
            and self.bottom > other.y
        )

    def intersection(self, other: "Rect") -> Optional["Rect"]:
        if not self.overlaps(other):
            return None
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        r = min(self.right, other.right)
        b = min(self.bottom, other.bottom)
        return Rect(x, y, r - x, b - y)

    def contains_y(self, y: float) -> bool:
        return self.y <= y <= self.bottom

    def overlap_ratio(self, other: "Rect") -> float:
        inter = self.intersection(other)
        if inter is None or self.area <= 0:
            return 0.0
        return inter.area / self.area

    def subtract(self, other: "Rect") -> list["Rect"]:
        inter = self.intersection(other)
        if inter is None or inter.area <= 0:
            return [self]
        pieces = []
        if inter.y > self.y:
            pieces.append(Rect(self.x, self.y, self.width, inter.y - self.y))
        if inter.bottom < self.bottom:
            pieces.append(Rect(self.x, inter.bottom, self.width, self.bottom - inter.bottom))
        if inter.x > self.x:
            pieces.append(Rect(self.x, inter.y, inter.x - self.x, inter.height))
        if inter.right < self.right:
            pieces.append(Rect(inter.right, inter.y, self.right - inter.right, inter.height))
        return pieces

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


def get_bounds(node: dict) -> Optional[Rect]:
    b = node.get("bounds")
    if b:
        return Rect(b["x"], b["y"], b["width"], b["height"])
    ls = node.get("layoutStyle")
    if ls:
        return Rect(
            ls.get("relativeX", 0),
            ls.get("relativeY", 0),
            ls.get("width", 0),
            ls.get("height", 0),
        )
    return None


def union_rect(rects: list[Rect]) -> Optional[Rect]:
    if not rects:
        return None
    x = min(r.x for r in rects)
    y = min(r.y for r in rects)
    r = max(r.right for r in rects)
    b = max(r.bottom for r in rects)
    return Rect(x, y, r - x, b - y)


# ---------------------------------------------------------------------------
# NodeIndex
# ---------------------------------------------------------------------------

class NodeIndex:
    """node 树索引。"""

    def __init__(self, root: dict):
        self.by_id: dict[str, dict] = {}
        self.parent: dict[str, Optional[str]] = {}
        self.depth: dict[str, int] = {}
        self._children: dict[str, list[str]] = {}
        self._walk(root, None, 0)

    def _walk(self, node: dict, parent_id: Optional[str], depth: int):
        nid = node["id"]
        self.by_id[nid] = node
        self.parent[nid] = parent_id
        self.depth[nid] = depth
        kids = []
        for child in node.get("children", []):
            kids.append(child["id"])
            self._walk(child, nid, depth + 1)
        self._children[nid] = kids

    def get(self, nid: str) -> Optional[dict]:
        return self.by_id.get(nid)

    def ancestors(self, nid: str) -> list[str]:
        result = []
        pid = self.parent.get(nid)
        while pid:
            result.append(pid)
            pid = self.parent.get(pid)
        return result

    def children(self, nid: str) -> list[str]:
        return self._children.get(nid, [])

    def collect_subtree_ids(self, nid: str) -> list[str]:
        ids = [nid]
        for cid in self._children.get(nid, []):
            ids.extend(self.collect_subtree_ids(cid))
        return ids

    def subtree_has_text(self, nid: str) -> bool:
        node = self.by_id.get(nid)
        if node is None:
            return False
        if node["type"] == "TEXT":
            return True
        for cid in self._children.get(nid, []):
            if self.subtree_has_text(cid):
                return True
        return False

    def subtree_text_ids(self, nid: str) -> set[str]:
        result: set[str] = set()
        node = self.by_id.get(nid)
        if node is None:
            return result
        if node["type"] == "TEXT" and (node.get("text") or "").strip():
            result.add(nid)
        for cid in self._children.get(nid, []):
            result.update(self.subtree_text_ids(cid))
        return result


# ---------------------------------------------------------------------------
# 结构指纹 & 重复检测
# ---------------------------------------------------------------------------

def make_fingerprint(node):
    sig = {"type": node.get("type")}
    children = node.get("children", [])
    if children:
        sig["children"] = [make_fingerprint(c) for c in children]
        sig["childCount"] = len(children)
    if node.get("type") == "TEXT":
        sig["isText"] = True
    return sig


def fingerprint_key(sig):
    return json.dumps(sig, sort_keys=True, ensure_ascii=False)


def detect_repeats(children):
    """检测连续结构指纹相同的子模块，返回去重列表。

    只有 CONTAINER_TYPES（GROUP/FRAME）能作为重复模板。
    TEXT/PATH/LAYER 等叶子节点不参与重复检测。
    """
    if len(children) <= 1:
        return children, False, 1

    fingerprints = []
    for c in children:
        if c["type"] in CONTAINER_TYPES:
            fingerprints.append(make_fingerprint(c))
        else:
            # 叶子节点：各自唯一
            fingerprints.append(None)

    deduped = []
    repeat_count = 0
    i = 0
    while i < len(children):
        deduped.append(children[i])
        fp = fingerprints[i]
        if fp is not None:
            j = i + 1
            while j < len(children) and fingerprints[j] is not None and fingerprint_key(fingerprints[j]) == fingerprint_key(fp):
                j += 1
            if j > i + 1:
                repeat_count = j - i
            i = j
        else:
            i += 1

    return deduped, repeat_count > 1, repeat_count if repeat_count > 1 else 1


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def resolve_path(project: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / project


def _node_refs(idx: NodeIndex, node_ids: list[str]) -> list[dict]:
    """将 nodeId 列表转为 [{nodeId, name}] 格式，方便对照 MasterGo 图层。"""
    result = []
    for nid in node_ids:
        node = idx.get(nid)
        name = (node.get("name") or "") if node else ""
        result.append({"nodeId": nid, "name": name})
    return result


def nearest_ancestor_of_type(idx: NodeIndex, nid: str, types: set) -> Optional[str]:
    for aid in idx.ancestors(nid):
        node = idx.get(aid)
        if node and node["type"] in types:
            return aid
    return None


def is_mask_like(node: dict) -> bool:
    if node.get("mask"):
        return True
    name = node.get("name", "")
    return any(kw in name for kw in ["Clip", "Mask", "蒙版"])


def _sibling_index(idx: NodeIndex, nid: str) -> int:
    pid = idx.parent.get(nid)
    if pid is None:
        return 0
    siblings = idx.children(pid)
    try:
        return siblings.index(nid)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# 分析：模板型
# ---------------------------------------------------------------------------

def analyze_template(
    entry: dict,
    root: dict,
    idx: NodeIndex,
    frame_area: float,
    judgments_map: dict[str, str],
    from_name_set: set[str] = None,
) -> dict:
    """模板型：fixed TEXT 容器 → fixedGroups，variable TEXT → slots（平铺）。"""
    if from_name_set is None:
        from_name_set = set()
    frame_id = entry.get("frameId", "")
    frame_name = entry.get("groupName", "")
    frame_width = entry.get("frameWidth", 0)

    # 统一重复检测：只处理模板实例（第一个）的 children
    children = root.get("children", [])
    deduped_children, repeatable, repeat_count = detect_repeats(children)
    if repeatable:
        deduped_ids = set()
        for child in deduped_children:
            deduped_ids.update(idx.collect_subtree_ids(child["id"]))
    else:
        deduped_ids = None

    all_text_nodes = [
        n for n in idx.by_id.values()
        if n["type"] == "TEXT" and (n.get("text") or "").strip()
        and (deduped_ids is None or n["id"] in deduped_ids)
    ]

    # 固定 TEXT → fixedGroups
    fixed_groups: list[dict] = []
    excluded_ids: set[str] = set()
    seen_containers: set[str] = set()

    for t in all_text_nodes:
        tid = t["id"]
        judgment = judgments_map.get(tid, "")
        if judgment != "fixed":
            continue

        container_id = None
        for aid in idx.ancestors(tid):
            node = idx.get(aid)
            if node is None or node["type"] not in CONTAINER_TYPES:
                continue
            text_ids_in = idx.subtree_text_ids(aid)
            has_var = any(judgments_map.get(stid) == "variable" for stid in text_ids_in)
            if not has_var:
                container_id = aid
                break

        if container_id is None:
            container_id = tid

        if container_id in seen_containers:
            continue
        seen_containers.add(container_id)

        container = idx.get(container_id)
        node_ids = idx.collect_subtree_ids(container_id)

        if container_id == tid:
            role = "fixed-texts"
        else:
            role = "fixed-texts"
            has_visual = any(
                idx.get(nid) and idx.get(nid)["type"] in VISUAL_TYPES
                for nid in node_ids if nid != container_id
            )
            if has_visual and container["type"] == "GROUP":
                role = "brand-badge"

        fixed_groups.append({
            "groupId": container_id,
            "groupName": container.get("name", ""),
            "role": role,
            "nodeIds": _node_refs(idx, node_ids),
            "reason": f"TEXT '{t['text']}' 为固定文案，连带容器整体固定",
        })
        excluded_ids.update(node_ids)

    # 可变 TEXT → slots（平铺，按 y 排序）
    slots = []
    for t in all_text_nodes:
        if judgments_map.get(t["id"]) == "variable":
            slots.append({
                "nodeId": t["id"],
                "name": (t.get("name") or "").strip(),
                "text": (t.get("text") or "").strip(),
            })

    # 处理 fromName 条目：nodeId 指向 GROUP/FRAME（文字被 MasterGo 转成了 PATH）
    for nid in from_name_set:
        node = idx.get(nid)
        if node is None or node["type"] not in CONTAINER_TYPES:
            continue
        judgment = judgments_map.get(nid, "")
        if judgment == "fixed":
            # GROUP 名称文字固定 → 容器整体入 fixedGroups
            node_ids = idx.collect_subtree_ids(nid)
            has_visual = any(
                idx.get(cid) and idx.get(cid)["type"] in VISUAL_TYPES
                for cid in node_ids if cid != nid
            )
            role = "brand-badge" if (has_visual and node["type"] == "GROUP") else "fixed-texts"
            fixed_groups.append({
                "groupId": nid,
                "groupName": node.get("name", ""),
                "role": role,
                "nodeIds": _node_refs(idx, node_ids),
                "reason": f"GROUP 名称 '{node.get('name','')}' 为固定文案（文字已转 PATH），连带容器整体固定",
            })
        elif judgment == "variable":
            # GROUP 名称文字可变 → 入 slots
            slots.append({
                "nodeId": nid,
                "name": (node.get("name") or "").strip(),
                "text": (node.get("name") or "").strip(),
            })

    slots.sort(key=lambda s: (
        get_bounds(idx.get(s["nodeId"])).y if get_bounds(idx.get(s["nodeId"])) else 0,
    ))

    return {
        "groupId": entry["groupId"],
        "groupName": entry["groupName"],
        "moduleIndexes": entry.get("moduleIndexes", []),
        "representativeIndex": entry.get("representativeIndex", 0),
        "frameType": "template",
        "repeatable": repeatable,
        "frameId": frame_id,
        "frameName": frame_name,
        "frameWidth": frame_width,
        "fixedGroups": fixed_groups,
        "slots": slots,
    }


# ---------------------------------------------------------------------------
# 分析：内容型
# ---------------------------------------------------------------------------

def analyze_content(entry: dict, root: dict, idx: NodeIndex, frame_area: float) -> dict:
    """内容型：纯几何分区。先检测重复子模块，再做遮挡计算找 zone。"""
    frame_id = entry.get("frameId", "")
    frame_name = entry.get("groupName", "")
    frame_width = entry.get("frameWidth", 0)

    # 检测重复子模块
    children = root.get("children", [])
    deduped_children, repeatable, repeat_count = detect_repeats(children)
    if repeatable:
        print(f"[INFO] {entry['groupName']}: 检测到 {repeat_count} 个重复子模块，取第一个为模板")

    # 从去重后的子树收集 TEXT（全部视为 variable）
    all_texts = []
    for child in deduped_children:
        all_texts.extend(_collect_text_nodes(child))

    # 从去重后的子树重建 node index（因为去重改变了树结构）
    # 直接用原始 root 的 idx，但只考虑 deduped children 的 nodeIds
    deduped_ids = set()
    for child in deduped_children:
        deduped_ids.update(idx.collect_subtree_ids(child["id"]))

    # fixedGroups：只检测蒙版和纯装饰容器
    fixed_groups: list[dict] = []
    excluded_ids: set[str] = set()

    for nid, node in idx.by_id.items():
        if nid not in deduped_ids:
            continue
        if is_mask_like(node) and node["type"] in CONTAINER_TYPES:
            mask_ids = idx.collect_subtree_ids(nid)
            deduped_mask_ids = [mid for mid in mask_ids if mid in deduped_ids]
            fixed_groups.append({
                "groupId": nid,
                "groupName": node.get("name", ""),
                "role": "mask",
                "nodeIds": _node_refs(idx, deduped_mask_ids),
                "reason": "蒙版组",
            })
            excluded_ids.update(deduped_mask_ids)

    # 收集有 fill 的 VISUAL 节点作为骨架候选
    # 只看大面积背景 LAYER/PATH，面积必须 >= 帧面积的 5%
    # 小面积元素（文字装饰、badge、线条）不参与分区
    min_candidate_area = frame_area * 0.05 if frame_area > 0 else 0

    skeleton_candidates: list[dict] = []
    for nid, node in idx.by_id.items():
        if nid not in deduped_ids:
            continue
        if nid in excluded_ids:
            continue
        if node["type"] not in VISUAL_TYPES:
            continue
        fill = node.get("fill")
        if not fill:
            continue
        # IMAGE fill 在蒙版组内 = 装饰图，不参与分区；不在蒙版内 = 正常背景
        if isinstance(fill, dict) and fill.get("type") == "IMAGE":
            ancestors = idx.ancestors(nid)
            if any(is_mask_like(idx.get(aid)) for aid in ancestors):
                continue
        bounds = get_bounds(node)
        if bounds is None or bounds.area <= 0:
            continue
        if bounds.area < min_candidate_area:
            continue

        # 有 TEXT 的 y 中心点落入
        has_text_inside = any(
            get_bounds(t_node) and bounds.contains_y(get_bounds(t_node).center_y)
            for t_node in all_texts
        )
        if not has_text_inside:
            continue

        skeleton_candidates.append({
            "nodeId": nid,
            "name": node.get("name", ""),
            "bounds": bounds,
            "depth": idx.depth[nid],
            "sibling_index": _sibling_index(idx, nid),
        })

    # 遮挡计算
    visible_skeletons = _compute_occlusion(idx, skeleton_candidates,
                                            min_occluder_area=frame_area * 0.05)

    # 合并为 zone，过滤太矮的 zone（固定 badge/标签，不是内容书写区）
    zones = _merge_into_zones(visible_skeletons, all_texts, idx)
    root_bounds = get_bounds(root)
    if root_bounds and root_bounds.height > 0:
        min_zone_h = root_bounds.height * 0.15
        zones = [z for z in zones
                 if (z["boundary"]["yEnd"] - z["boundary"]["yStart"]) >= min_zone_h]

    excluded_ids.update(s["nodeId"] for s in visible_skeletons)

    # 检测 zone 外的固定 UI：TEXT 不在任何 zone slot 里 → 向上找容器 → fixedGroup
    zone_slot_ids: set[str] = set()
    for z in zones:
        for s in z.get("slots", []):
            zone_slot_ids.add(s["nodeId"])

    used_containers: set[str] = set()
    for t in all_texts:
        tid = t["id"]
        if tid in zone_slot_ids or tid in excluded_ids:
            continue
        # TEXT 不在任何 zone 里 → 固定文字，找最外层不含 zone TEXT 的容器
        container_id = None
        for aid in idx.ancestors(tid):
            node = idx.get(aid)
            if node is None or node["type"] not in CONTAINER_TYPES:
                continue
            text_ids_in = idx.subtree_text_ids(aid)
            has_zone_text = any(stid in zone_slot_ids for stid in text_ids_in)
            if not has_zone_text:
                container_id = aid  # 继续往上找，不 break
        if container_id is None:
            container_id = tid
        if container_id in used_containers:
            continue
        used_containers.add(container_id)

        container = idx.get(container_id)
        container_ids = idx.collect_subtree_ids(container_id)
        has_visual = any(
            idx.get(cid) and idx.get(cid)["type"] in VISUAL_TYPES
            for cid in container_ids if cid != container_id
        )
        role = "fixed-label" if (has_visual and container["type"] == "GROUP") else "fixed-texts"
        fixed_groups.append({
            "groupId": container_id,
            "groupName": container.get("name", ""),
            "role": role,
            "nodeIds": _node_refs(idx, container_ids),
            "reason": "TEXT '%s' 在 zone 外，为固定 UI 元素" % (t.get("text", "") or "")[:30],
        })
        excluded_ids.update(container_ids)

    return {
        "groupId": entry["groupId"],
        "groupName": entry["groupName"],
        "moduleIndexes": entry.get("moduleIndexes", []),
        "representativeIndex": entry.get("representativeIndex", 0),
        "frameType": "content",
        "repeatable": repeatable or entry.get("repeatable", False),
        "frameId": frame_id,
        "frameName": frame_name,
        "frameWidth": frame_width,
        "fixedGroups": fixed_groups,
        "zones": zones,
        "_all_texts": all_texts,  # 仅用于审阅文件生成，不入最终输出
    }


def _collect_text_nodes(node):
    """递归收集 TEXT 节点。"""
    results = []
    if node.get("type") == "TEXT" and (node.get("text") or "").strip():
        results.append(node)
    for child in node.get("children", []):
        results.extend(_collect_text_nodes(child))
    return results


def _compute_occlusion(idx: NodeIndex, candidates: list[dict],
                        min_occluder_area: float = 0) -> list[dict]:
    """全局 z-order 遮挡计算。

    深度优先遍历整棵树，后面的节点遮挡前面的（不管层级）。
    蒙版（mask/Clip）节点不参与遮挡。面积小于 min_occluder_area 的节点不遮挡。
    """
    # 构建全局 z-order（深度优先预序遍历所有节点）
    global_order: list[str] = []
    def walk(nid: str):
        global_order.append(nid)
        for cid in idx.children(nid):
            walk(cid)
    # 从根节点开始遍历
    root_id = None
    for nid in idx.by_id:
        if idx.parent.get(nid) is None:
            root_id = nid
            break
    if root_id:
        walk(root_id)

    # 构建 nodeId → global z-index 映射
    z_index: dict[str, int] = {nid: i for i, nid in enumerate(global_order)}

    # 预计算所有可能遮挡物的 bounds
    # 只有确实渲染像素的节点才能遮挡：VISUAL_TYPES 有 fill，或容器有 fill
    # TEXT 节点、空 GROUP、蒙版内节点都不参与遮挡
    all_occluder_bounds: list[tuple[int, Rect]] = []
    for nid in global_order:
        node = idx.get(nid)
        if node is None or is_mask_like(node):
            continue
        # 蒙版祖先内的节点不参与遮挡
        ancestors = idx.ancestors(nid)
        if any(is_mask_like(idx.get(aid)) for aid in ancestors):
            continue
        # 必须有 fill 且面积 ≥ min_occluder_area 才能遮挡
        # IMAGE fill 在蒙版内 = 装饰图，不参与遮挡
        fill = node.get("fill")
        if not fill:
            continue
        if isinstance(fill, dict) and fill.get("type") == "IMAGE":
            ancestors = idx.ancestors(nid)
            if any(is_mask_like(idx.get(aid)) for aid in ancestors):
                continue
        b = get_bounds(node)
        if b and b.area > 0 and (min_occluder_area <= 0 or b.area >= min_occluder_area):
            all_occluder_bounds.append((z_index[nid], b))

    visible = []
    for item in candidates:
        nid = item["nodeId"]
        bounds = item["bounds"]
        zi = z_index.get(nid, 0)

        # 收集所有 z-order 在 nid 之后的遮挡物
        occluders = [b for (zj, b) in all_occluder_bounds if zj > zi]

        remaining = [bounds]
        for occ in occluders:
            new_remaining = []
            for r in remaining:
                new_remaining.extend(r.subtract(occ))
            remaining = new_remaining
            if not remaining:
                break

        total = sum(r.area for r in remaining)
        if bounds.area > 0 and total / bounds.area >= 0.15:
            item["visibleRects"] = remaining
            visible.append(item)

    return visible


def _merge_into_zones(
    skeletons: list[dict],
    texts: list[dict],
    idx: NodeIndex,
) -> list[dict]:
    """合并重叠骨架为 zone，分配 TEXT。"""
    if not skeletons:
        return []

    skeletons.sort(key=lambda s: s["bounds"].y)
    n = len(skeletons)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    for i in range(n):
        for j in range(i + 1, n):
            # 用可见 rects 合并后的 bounds 来判断重叠，不是原始 bounds
            rects_i = skeletons[i].get("visibleRects", [skeletons[i]["bounds"]])
            rects_j = skeletons[j].get("visibleRects", [skeletons[j]["bounds"]])
            ui = union_rect(rects_i)
            uj = union_rect(rects_j)
            if ui is None or uj is None:
                continue
            ratio_i = ui.overlap_ratio(uj)
            ratio_j = uj.overlap_ratio(ui)
            if ratio_i >= 0.90 or ratio_j >= 0.90:
                union(i, j)

    # 形成初始分组
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root_idx = find(i)
        groups.setdefault(root_idx, []).append(i)

    # 第二轮：间距合并（相邻组 y 间隙 ≤ 15px 也合并，如标题与副标题）
    sorted_roots = sorted(groups.keys(), key=lambda r: min(skeletons[i]["bounds"].y for i in groups[r]))
    merged = True
    while merged:
        merged = False
        for k in range(len(sorted_roots) - 1):
            ra, rb = sorted_roots[k], sorted_roots[k + 1]
            # 找到两组的边界（用可见 rects 的合成 bounds）
            group_a = groups[ra]
            group_b = groups[rb]
            ua = union_rect([r for i in group_a for r in skeletons[i].get("visibleRects", [skeletons[i]["bounds"]])])
            ub = union_rect([r for i in group_b for r in skeletons[i].get("visibleRects", [skeletons[i]["bounds"]])])
            if ua is None or ub is None:
                continue
            bottom_a = ua.bottom
            top_b = ub.y
            gap = top_b - bottom_a
            if 0 < gap <= 15:
                # 合并 group_b 到 group_a
                groups[ra].extend(groups[rb])
                del groups[rb]
                sorted_roots.remove(rb)
                merged = True
                break

    zones = []
    seen_text_ids: set[str] = set()
    zone_idx = 0
    for root_key in sorted(groups.keys(), key=lambda r: min(skeletons[i]["bounds"].y for i in groups[r])):
        indices = groups[root_key]
        members = [skeletons[i] for i in indices]
        all_rects = [r for m in members for r in m.get("visibleRects", [m["bounds"]])]
        union_bounds = union_rect(all_rects)
        if union_bounds is None:
            continue

        # 每个 skeleton 节点的可见碎片合并为一个整体 visibleRect
        skeleton_layers = []
        for m in members:
            rects = m.get("visibleRects", [])
            if not rects:
                continue
            merged = union_rect(rects)
            if merged is None:
                continue
            skeleton_layers.append({
                "nodeId": m["nodeId"],
                "name": m["name"],
                "visibleRect": merged.to_dict(),
            })

        slots = []
        slot_rects = []
        for t in texts:
            tb = get_bounds(t)
            if tb is None:
                continue
            if union_bounds.contains_y(tb.center_y):
                slots.append({
                    "nodeId": t["id"],
                    "name": (t.get("name") or "").strip(),
                    "text": (t.get("text") or "").strip(),
                })
                slot_rects.append(tb)

        # 每个 TEXT 只归入一个 zone
        paired = [(s, r) for s, r in zip(slots, slot_rects)
                  if s["nodeId"] not in seen_text_ids]
        slots = [s for s, _ in paired]
        slot_rects = [r for _, r in paired]
        seen_text_ids.update(s["nodeId"] for s in slots)

        slots.sort(key=lambda s: (
            get_bounds(idx.get(s["nodeId"])).y if get_bounds(idx.get(s["nodeId"])) else 0,
            get_bounds(idx.get(s["nodeId"])).x if get_bounds(idx.get(s["nodeId"])) else 0,
        ))

        # 固定内边距：可写区域 = zone boundary 往内缩 CONTENT_PADDING
        pad = CONTENT_PADDING
        content_area = Rect(
            union_bounds.x + pad,
            union_bounds.y + pad,
            max(0, union_bounds.width - pad * 2),
            max(0, union_bounds.height - pad * 2),
        )
        padding = {"top": pad, "bottom": pad, "left": pad, "right": pad}

        # 判断文字对齐：所有 slot TEXT 的 x 中心都靠近 boundary 中心 → 居中
        alignment = "left"
        if slot_rects:
            bcx = union_bounds.x + union_bounds.width / 2
            all_centered = all(
                abs(r.x + r.width / 2 - bcx) < union_bounds.width * 0.15
                for r in slot_rects
            )
            if all_centered:
                alignment = "center"

        zones.append({
            "id": f"zone-{zone_idx}",
            "boundary": {
                "xStart": union_bounds.x,
                "xEnd": union_bounds.right,
                "yStart": union_bounds.y,
                "yEnd": union_bounds.bottom,
            },
            "skeletonLayers": skeleton_layers,
            "slots": slots,
            "contentArea": content_area.to_dict() if content_area else None,
            "padding": padding,
            "textAlign": alignment,
        })
        zone_idx += 1

    return zones


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Step 2 Phase 1: 构建 slots-definition.json")
    parser.add_argument("--project", required=True, help="项目名，如 huaxia-hot-citc")
    args = parser.parse_args()

    base = resolve_path(args.project)
    frame_types_path = base / "output" / "step2-01_frame-types.json"
    judgments_path = base / "output" / "step2-02_text-judgments.json"
    index_path = base / "modules" / "_index.json"
    modules_dir = base / "modules"
    output_path = base / "output" / "step2-04_slots-definition.json"

    frame_types_data = json.loads(frame_types_path.read_text(encoding="utf-8"))
    index_data = json.loads(index_path.read_text(encoding="utf-8"))

    # 加载 judgments（如果存在）
    judgments_map: dict[str, str] = {}
    from_name_set: set[str] = set()  # nodeId 来自 GROUP 名称而非 TEXT 节点
    if judgments_path.exists():
        judgments_data = json.loads(judgments_path.read_text(encoding="utf-8"))
        for frame_name, frame_data in judgments_data.get("frames", {}).items():
            for entry in frame_data.get("texts", []):
                nid = entry.get("nodeId", "")
                judgment = entry.get("judgment", "")
                if nid and judgment in ("fixed", "variable"):
                    judgments_map[nid] = judgment
                    if entry.get("fromName"):
                        from_name_set.add(nid)

    # Build module lookup
    module_lookup = {}
    for m in index_data["modules"]:
        module_lookup[m["moduleIndex"]] = m

    modules_out = []
    for entry in frame_types_data.get("frames", []):
        frame_type = entry.get("frameType", "")

        # Resolve module JSON path
        module_json_path = None
        file_name = Path(entry["moduleJson"]).name
        candidate = modules_dir / file_name
        if candidate.exists():
            module_json_path = candidate
        else:
            print(f"[WARN] 找不到 {entry['moduleJson']}，跳过 {entry['groupName']}")
            continue

        module = json.loads(module_json_path.read_text(encoding="utf-8"))
        root = module["node"]
        idx = NodeIndex(root)
        frame_bounds = get_bounds(root)
        frame_area = frame_bounds.area if frame_bounds else 0

        # 补充 entry 中缺失的字段
        entry["frameId"] = module["meta"]["moduleId"]
        entry["frameWidth"] = module["meta"]["position"]["width"]

        # Find matching group in index for moduleIndexes
        group_name = entry["groupName"]
        # We don't have moduleIndexes from frame-types, get from _index
        entry["moduleIndexes"] = [m["moduleIndex"] for m in index_data["modules"]
                                   if m["moduleName"] == group_name
                                   or Path(m["fileName"]).stem.startswith(group_name)]
        if not entry["moduleIndexes"]:
            entry["moduleIndexes"] = [0]  # fallback
        entry["representativeIndex"] = entry["moduleIndexes"][0] if entry["moduleIndexes"] else 0

        if frame_type == "fully-fixed":
            all_ids = idx.collect_subtree_ids(root["id"])
            modules_out.append({
                "groupId": entry["groupId"],
                "groupName": entry["groupName"],
                "moduleIndexes": entry["moduleIndexes"],
                "representativeIndex": entry["representativeIndex"],
                "fullyFixed": True,
                "frameId": entry["frameId"],
                "frameName": entry["groupName"],
                "frameWidth": entry["frameWidth"],
                "fixedGroups": [{
                    "groupId": root["id"],
                    "groupName": entry["groupName"],
                    "role": "fully-fixed-frame",
                    "nodeIds": _node_refs(idx, all_ids),
                    "reason": "完全固定 frame：无可变内容",
                }],
                "zones": [],
            })

        elif frame_type == "template":
            result = analyze_template(entry, root, idx, frame_area, judgments_map, from_name_set)
            modules_out.append(result)

        elif frame_type == "content":
            result = analyze_content(entry, root, idx, frame_area)
            modules_out.append(result)

        else:
            print(f"[WARN] {entry['groupName']}: frameType 未填写或无效 ('{frame_type}')，跳过")

    # ---- Phase 1b AI 审阅：读取已有判断 + 生成审阅文件 + 应用 ----
    review_path = base / "output" / "step2-03_content-zones.json"
    review_map: dict[str, dict[str, bool]] = {}
    if review_path.exists():
        review_data = json.loads(review_path.read_text(encoding="utf-8"))
        for fr in review_data.get("frames", []):
            zone_keeps = {}
            for zr in fr.get("zones", []):
                if zr.get("keep") == "true":
                    zone_keeps[zr["id"]] = True
                elif zr.get("keep") == "false":
                    zone_keeps[zr["id"]] = False
            review_map[fr["groupName"]] = zone_keeps

    review_frames = []
    for m in modules_out:
        if m.get("frameType") != "content":
            continue
        all_texts = m.pop("_all_texts", [])
        kept = review_map.get(m["groupName"], {})
        zones_review = []
        for z in m.get("zones", []):
            zid = z["id"]
            zh = z["boundary"]["yEnd"] - z["boundary"]["yStart"]
            zy = z["boundary"]["yStart"]
            samples = []
            for tn in all_texts:
                tb = get_bounds(tn)
                if tb and zy <= tb.center_y <= zy + zh:
                    samples.append((tn.get("text") or "").strip()[:40])
            existing = kept.get(zid)
            keep_val = ""
            if existing is True:
                keep_val = "true"
            elif existing is False:
                keep_val = "false"
            zones_review.append({
                "id": zid,
                "height": round(zh, 0),
                "sampleSlots": samples[:3],
                "keep": keep_val,
            })
        if zones_review:
            review_frames.append({"groupName": m["groupName"], "zones": zones_review})
        # 应用 AI 过滤
        if kept:
            m["zones"] = [z for z in m.get("zones", [])
                          if kept.get(z["id"]) is not False]

    if review_frames:
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps(
            {"frames": review_frames}, ensure_ascii=False, indent=2), encoding="utf-8")

    output = {"modules": modules_out}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    fixed_count = sum(1 for m in modules_out if m.get("fullyFixed"))
    template_count = sum(1 for m in modules_out if m.get("frameType") == "template")
    content_count = sum(1 for m in modules_out if m.get("frameType") == "content")
    zone_count = sum(len(m.get("zones", [])) for m in modules_out)
    slot_count = sum(
        len(m.get("slots", [])) + sum(len(z.get("slots", [])) for z in m.get("zones", []))
        for m in modules_out
    )
    print(
        f"[OK] {len(modules_out)} 个模块 → {output_path}"
    )
    print(
        f"    固定: {fixed_count} | 模板型: {template_count} | 内容型: {content_count} | "
        f"zone: {zone_count} | slot: {slot_count}"
    )


if __name__ == "__main__":
    main()
