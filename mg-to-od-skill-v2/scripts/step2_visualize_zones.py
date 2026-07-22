"""
Step 2 可视化：生成 frame 分区框线图 HTML（只展示 zone 矩形框）。

Usage:
  python scripts/step2_visualize_zones.py --project huaxia-hot-citc
"""

import json
import argparse
from pathlib import Path


COLORS = [
    "rgba(255,99,132,0.25)", "rgba(54,162,235,0.25)", "rgba(255,206,86,0.25)",
    "rgba(75,192,192,0.25)", "rgba(153,102,255,0.25)", "rgba(255,159,64,0.25)",
]
BORDERS = [
    "rgba(255,99,132,0.9)", "rgba(54,162,235,0.9)", "rgba(255,206,86,0.9)",
    "rgba(75,192,192,0.9)", "rgba(153,102,255,0.9)", "rgba(255,159,64,0.9)",
]


def resolve_path(project: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / project


def main():
    parser = argparse.ArgumentParser(description="Step 2 可视化 zone 分区")
    parser.add_argument("--project", required=True, help="项目名")
    args = parser.parse_args()

    base = resolve_path(args.project)
    slots_path = base / "output" / "step2-04_slots-definition.json"
    modules_dir = base / "modules"
    output_path = base / "output" / "step2-05_zone-visualization.html"

    data = json.loads(slots_path.read_text(encoding="utf-8"))
    modules = data.get("modules", [])

    # Load module JSONs to get frame absolute positions for normalization
    module_positions = {}
    for mf in modules_dir.glob("*.json"):
        if mf.name.startswith("_"):
            continue
        mod = json.loads(mf.read_text(encoding="utf-8"))
        mod_id = mod["meta"]["moduleId"]
        mod_pos = mod["meta"]["position"]
        module_positions[mod_id] = {
            "x": mod_pos.get("x", 0),
            "y": mod_pos["y"],
            "width": mod_pos["width"],
            "height": mod_pos["height"],
            "name": mod["meta"]["moduleName"],
        }

    html_parts = []
    for m in modules:
        fid = m.get("frameId", "")
        finfo = module_positions.get(fid)
        if not finfo:
            html_parts.append(f"<p style='color:red'>找不到 frameId={fid} 的模块 JSON</p>")
            continue

        frame_width = m.get("frameWidth", finfo["width"])
        frame_type = m.get("frameType") or ("fully-fixed" if m.get("fullyFixed") else "?")
        frame_y = finfo["y"]
        frame_h = finfo["height"]

        # Normalize zone coordinates relative to frame top-left
        zones = m.get("zones", [])
        fixed_groups = m.get("fixedGroups", [])

        # Find the bottom-most content to determine display height
        if zones:
            max_zone_end = max(z["boundary"]["yEnd"] for z in zones)
            frame_h = max(frame_h, max_zone_end - frame_y)
        elif m.get("slots"):
            # For template-type without zones, frame height is just the frame height
            pass

        # Scale to fit
        scale = min(700 / frame_width, 1.0) if frame_width > 0 else 1
        display_w = frame_width * scale
        display_h = frame_h * scale

        zone_html = ""
        for zi, z in enumerate(zones):
            color = COLORS[zi % len(COLORS)]
            border = BORDERS[zi % len(BORDERS)]

            # Normalize y to relative (frame-local)
            rel_y = z["boundary"]["yStart"] - frame_y
            rel_h = z["boundary"]["yEnd"] - z["boundary"]["yStart"]

            top = rel_y * scale
            height = rel_h * scale
            left = 0
            width = display_w

            yn_start = z["boundary"]["yStart"]
            yn_end = z["boundary"]["yEnd"]
            slot_count = len(z.get("slots", []))
            skeleton_count = len(z.get("skeletonLayers", []))

            # contentArea: 文字实际可写区域（相对 frame 坐标）
            ca_html = ""
            ca = z.get("contentArea")
            pad = z.get("padding")
            frame_x = finfo.get("x", 0)
            if ca:
                ca_rel_x = ca["x"] - frame_x
                ca_rel_y = ca["y"] - frame_y
                ca_left = ca_rel_x * scale
                ca_top = ca_rel_y * scale
                ca_w = ca["width"] * scale
                ca_h = ca["height"] * scale
                pad_info = ""
                if pad:
                    pad_info = f'上{pad["top"]:.0f} 下{pad["bottom"]:.0f} 左{pad["left"]:.0f} 右{pad["right"]:.0f}'
                ca_html = f"""
              <div style="position:absolute;left:{ca_left:.1f}px;top:{ca_top:.1f}px;
                          width:{ca_w:.1f}px;height:{ca_h:.1f}px;
                          background:rgba(50,205,50,0.12);border:2px dashed rgba(50,205,50,0.6);
                          box-sizing:border-box;">
                <span style="position:absolute;top:-14px;left:2px;font-size:8px;color:#2d7d2d;
                             white-space:nowrap;">
                  {ca["width"]:.0f}x{ca["height"]:.0f}
                </span>
                <span style="position:absolute;bottom:-14px;right:2px;font-size:8px;color:#555;
                             white-space:nowrap;">
                  {pad_info}
                </span>
              </div>"""

            zone_html += f"""
            <div style="position:absolute;left:{left}px;top:{top}px;width:{width}px;height:{height}px;
                        background:{color};border:2px solid {border};box-sizing:border-box;">
              <span style="position:absolute;top:2px;left:6px;font-size:11px;font-weight:600;
                           background:white;padding:1px 6px;border-radius:3px;color:#333;">
                {z['id']}
              </span>
              <span style="position:absolute;bottom:2px;right:6px;font-size:9px;color:#666;
                           background:rgba(255,255,255,0.8);padding:1px 4px;border-radius:2px;">
                y:{yn_start:.0f}→{yn_end:.0f} ({rel_h:.0f}px) | {slot_count} slot(s) | {skeleton_count} layers
              </span>
              {ca_html}
            </div>"""

        # Build info line for fixed groups
        fg_info = ""
        if fixed_groups:
            roles = [f"{fg['role']}:{fg['groupName'][:15]}" for fg in fixed_groups]
            fg_info = f" | fixedGroups: {', '.join(roles[:3])}"

        # Build slot count for template-type
        slot_info = ""
        if m.get("slots"):
            slot_info = f" | {len(m['slots'])} slot(s) 平铺"

        html_parts.append(f"""
        <div style="margin-bottom:36px;font-family:monospace;">
          <div style="margin-bottom:6px;">
            <strong>{m.get('groupName','')}</strong>
            <span style="color:#888;font-size:12px;">
              [{frame_type}{' · repeatable' if m.get('repeatable') else ''}]
              {fid} | {frame_width:.0f}x{frame_h:.0f}px
              {fg_info}{slot_info}
            </span>
          </div>
          <div style="position:relative;width:{display_w}px;height:{display_h}px;
                      border:2px solid #333;background:#fafafa;overflow:hidden;">
            {zone_html if zone_html else '<div style="padding:20px;color:#aaa;font-size:13px;">无 zone（固定模块或模板型）</div>'}
          </div>
        </div>""")

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Step 2 Zone 分区可视化 — {args.project}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 800px; margin: 20px auto; padding: 0 20px; background: #fff; color: #333; }}
  h2 {{ border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 24px; }}
  .legend {{ color: #888; font-size: 13px; margin-bottom: 24px; line-height: 1.6; }}
</style>
</head>
<body>
<h2>Step 2 Zone 分区可视化 — {args.project}</h2>
<div class="legend">
  🟥 色块 = zone 区域 | 黑框 = frame 边界<br>
  每块显示 zone id、y 范围、slot 数量、skeleton layer 数量
</div>
{''.join(html_parts)}
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_html, encoding="utf-8")
    print(f"[OK] → {output_path}")
    print(f"     共 {len(modules)} 个模块 | 请在浏览器中打开查看")


if __name__ == "__main__":
    main()
