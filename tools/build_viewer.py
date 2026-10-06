#!/usr/bin/env python3
"""data/chart-storyNN.json から、通し番号つきの閲覧ページ viewer/chart-storyNN.html を生成する。

使い方: python3 -I tools/build_viewer.py data/chart-story01.json
"""
import collections
import html
import json
import os
import sys

def num_str(n):
    return f'<span class="no">{n}</span>'


def owner(titles, y):
    above = [t for t in sorted(titles, key=lambda t: t['y']) if t['y'] <= y + 4]
    return above[-1]['n'] if above else None


def build_area(area):
    # 1) ラベルを (マップ, 相手, 連番) に分解
    ends = collections.OrderedDict()
    for img in area['images']:
        for lab in img['labels']:
            n = owner(img['titles'], lab['box'][1])
            if n is None:
                continue
            b, k = (int(x) for x in lab['text'].split('-'))
            lab['_owner'] = n
            ends.setdefault((n, b, k), []).append(lab)
    # 2) 両端が揃ったペアに通し番号。片端だけのものは「要確認」
    pairs = {}
    for (n, b, k) in ends:
        key = (min(n, b), max(n, b), k)
        pairs.setdefault(key, set()).add(n)
    numbering, unmatched = {}, []
    for key in sorted(pairs):
        lo, hi, _ = key
        if len(pairs[key]) == (1 if lo == hi else 2):
            numbering[key] = len(numbering) + 1
        else:
            unmatched.append(key)
    for (n, b, k), labs in ends.items():
        key = (min(n, b), max(n, b), k)
        for lab in labs:
            lab['_no'] = numbering.get(key)
            lab['_dest'] = b
    return numbering, unmatched, ends


def diagram(numbering, unmatched):
    """マップ間の接続図(SVG)。BFS の層を左→右に並べ、線の中央に通し番号を置く。"""
    edges = [(lo, hi, no, False) for (lo, hi, _), no in numbering.items() if lo != hi]
    edges += [(lo, hi, None, True) for lo, hi, _ in unmatched if lo != hi]
    nodes = sorted({n for e in edges for n in e[:2]})
    if not edges:
        return ''
    adj = collections.defaultdict(set)
    for lo, hi, _, _ in edges:
        adj[lo].add(hi)
        adj[hi].add(lo)
    layer = {}
    for root in nodes:
        if root in layer:
            continue
        layer[root] = 0
        queue = collections.deque([root])
        while queue:
            cur = queue.popleft()
            for nxt in sorted(adj[cur]):
                if nxt not in layer:
                    layer[nxt] = layer[cur] + 1
                    queue.append(nxt)
    cols = collections.defaultdict(list)
    for n in nodes:
        cols[layer[n]].append(n)
    bw, bh, gx, gy = 64, 28, 56, 20
    pos = {}
    for c, members in cols.items():
        for r, n in enumerate(members):
            pos[n] = (12 + c * (bw + gx), 12 + r * (bh + gy))
    width = 24 + (max(cols) + 1) * (bw + gx) - gx
    height = 24 + max(len(m) for m in cols.values()) * (bh + gy) - gy
    parts = [f'<svg class="graph" viewBox="0 0 {width} {height}" role="img" aria-label="マップ間の接続図">']
    for lo, hi, no, warn in edges:
        (x1, y1), (x2, y2) = pos[lo], pos[hi]
        ax, ay, bx, by = x1 + bw / 2, y1 + bh / 2, x2 + bw / 2, y2 + bh / 2
        parts.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" class="edge{" warn" if warn else ""}"/>')
    for lo, hi, no, warn in edges:
        (x1, y1), (x2, y2) = pos[lo], pos[hi]
        mx, my = (x1 + x2) / 2 + bw / 2, (y1 + y2) / 2 + bh / 2
        parts.append(f'<g class="el{" warn" if warn else ""}"><rect x="{mx - 9}" y="{my - 8}" width="18" height="16" rx="8"/><text x="{mx}" y="{my + 4}">{no if no else "?"}</text></g>')
    for n, (x, y) in pos.items():
        parts.append(f'<g class="node"><rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4"/><text x="{x + bw / 2}" y="{y + 18}">マップ{n}</text></g>')
    parts.append('</svg>')
    return ''.join(parts)


def render(data):
    base = data['base']
    out = []
    for area in data['areas']:
        numbering, unmatched, ends = build_area(area)
        out.append(f'<section id="{area["id"]}"><h2>{html.escape(area["name"])}</h2>')
        out.append(diagram(numbering, unmatched))
        for img in area['images']:
            w, h = img['w'], img['h']
            out.append(f'<figure><figcaption>{html.escape(img["alt"])}</figcaption>')
            out.append(f'<div class="map" style="max-width:{w}px"><img src="{base}{img["file"]}" width="{w}" height="{h}" loading="lazy" alt="{html.escape(img["alt"])}">')
            for lab in img['labels']:
                if '_owner' not in lab:
                    continue
                x0, y0, x1, y1 = lab['box']
                cx, cy = (x0 + x1) / 2 / w * 100, (y0 + y1) / 2 / h * 100
                no = lab['_no']
                head = f'#{no}' if no else '？'
                cls = 'badge' if no else 'badge warn'
                tip = f'旧表記 {lab["text"]}（マップ{lab["_owner"]} → マップ{lab["_dest"]}）'
                out.append(f'<span class="{cls}" style="left:{cx:.2f}%;top:{cy:.2f}%" title="{tip}"><b>{head}</b><i>→{lab["_dest"]}</i></span>')
            out.append('</div></figure>')
        rows = []
        for key, no in sorted(numbering.items(), key=lambda t: t[1]):
            lo, hi, k = key
            a_old, b_old = f'{hi}-{k}', f'{lo}-{k}'
            if lo == hi:
                rows.append(f'<tr><th>{num_str(no)}</th><td>マップ{lo} 内</td><td>{lo}-{k}</td></tr>')
            else:
                rows.append(f'<tr><th>{num_str(no)}</th><td>マップ{lo} ⇄ マップ{hi}</td><td>マップ{lo}側「{a_old}」／マップ{hi}側「{b_old}」</td></tr>')
        for lo, hi, k in unmatched:
            rows.append(f'<tr class="warn"><th>？</th><td>マップ{lo} ⇄ マップ{hi}</td><td>旧表記 {hi}-{k} / {lo}-{k}（片側のラベルが画像から読み取れず要確認）</td></tr>')
        out.append('<table><thead><tr><th>番号</th><th>つながり</th><th>画像内の旧表記</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></section>')
    return '\n'.join(out)


PAGE = '''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page} 接続マップ</title>
<style>
:root{{--bg:#fff;--fg:#222;--sub:#666;--line:#ddd;--badge:#c2185b;--warn:#e65100}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181d;--fg:#e8e8e8;--sub:#a0a0a0;--line:#3a3d45;--badge:#f06292;--warn:#ffb74d}}}}
body{{margin:0 auto;padding:16px;max-width:760px;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif}}
h1{{font-size:20px}} h2{{font-size:18px;border-bottom:2px solid var(--line);padding-bottom:4px;margin-top:40px}}
.note{{background:rgba(128,128,128,.12);padding:10px 14px;border-radius:6px;font-size:14px}}
figure{{margin:16px 0}} figcaption{{color:var(--sub);font-size:13px}}
.map{{position:relative;line-height:0}} .map img{{width:100%;height:auto;display:block}}
.badge{{position:absolute;transform:translate(-50%,-50%);background:var(--badge);color:#fff;border-radius:11px;padding:1px 6px;line-height:1.3;font-size:12px;white-space:nowrap;box-shadow:0 0 0 2px #fff;cursor:help}}
.badge b{{font-size:14px}} .badge i{{font-style:normal;margin-left:3px;font-size:11px}}
.badge.warn{{background:var(--warn)}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:12px}} th,td{{border:1px solid var(--line);padding:4px 8px;text-align:left}}
tr.warn{{color:var(--warn)}}
.graph{{width:100%;max-width:640px;height:auto;margin:8px 0}}
.graph .edge{{stroke:var(--sub);stroke-width:1.5}} .graph .edge.warn{{stroke:var(--warn);stroke-dasharray:4 3}}
.graph .node rect{{fill:var(--bg);stroke:var(--fg);stroke-width:1.5}} .graph .node text{{fill:var(--fg);font-size:12px;text-anchor:middle}}
.graph .el rect{{fill:var(--badge)}} .graph .el.warn rect{{fill:var(--warn)}} .graph .el text{{fill:#fff;font-size:11px;font-weight:700;text-anchor:middle}}
.no{{display:inline-block;min-width:1.6em;text-align:center;background:var(--badge);color:#fff;border-radius:1em;padding:0 4px;font-weight:700}}
</style></head><body>
<h1>{page} 接続マップ（通し番号版）</h1>
<p class="note">同じ番号の出入口どうしがつながっています。「→N」は行き先のマップ番号です。バッジにカーソルを重ねると元画像の表記（例: 2-1）が出ます。画像・内容は <a href="{source}">元ページ</a> のもので、個人利用の閲覧補助です。</p>
{body}
</body></html>
'''


def main():
    path = sys.argv[1]
    data = json.load(open(path, encoding='utf-8'))
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), 'viewer')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, data['page'] + '.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(PAGE.format(page=data['page'], source=data['source'], body=render(data)))
    print(out)


if __name__ == '__main__':
    main()
