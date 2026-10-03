# -*- coding: utf-8 -*-
"""
生成平台展示页 app/showcase.html（自包含，无外部依赖）
内容反映真实架构：数据接入 → 本体性转化 → 统一语义图 → 工具接口 → MCP 网关
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiplatform.core import PlatformOntology, SourceCatalog, UnifiedGraph
from aiplatform.build_platform import build
from aiplatform.tools import PlatformTools

def bars(items, key, val, unit="篇"):
    if not items:
        return "<p style='color:#888'>无数据</p>"
    mx = max(float(x[val] or 0) for x in items) or 1
    rows = []
    for x in items:
        v = float(x[val] or 0)
        w = max(5, int(v / mx * 100))
        rows.append(f"<div class='bar-row'><span class='bar-label'>{x[key]}</span>"
                    f"<span class='bar-track'><span class='bar-fill' style='width:{w}%'></span></span>"
                    f"<span class='bar-val'>{x[val]}</span></div>")
    return "".join(rows)

def bars_simple(items):
    if not items:
        return "<p style='color:#888'>无数据</p>"
    mx = max(len(v) for _, v in items) or 1
    rows = []
    for k, v in items:
        w = max(5, int(len(v) / mx * 100))
        rows.append(f"<div class='bar-row'><span class='bar-label'>{k}</span>"
                    f"<span class='bar-track'><span class='bar-fill' style='width:{w}%'></span></span>"
                    f"<span class='bar-val'>{len(v)}</span></div>")
    return "".join(rows)

def trend(items):
    if not items:
        return "<p style='color:#888'>无数据</p>"
    mx = max(int(x["papers"]) for x in items) or 1
    cols = []
    for r in items:
        h = max(8, int(int(r["papers"]) / mx * 140))
        cols.append(f"<div class='trend-col'><div class='trend-bar' style='height:{h}px'></div>"
                    f"<div class='trend-year'>{r['year']}</div><div class='trend-val'>{r['papers']}</div></div>")
    return f"<div class='trend-wrap'>{''.join(cols)}</div>"

def main():
    onto, cat, graph = build()
    pt = PlatformTools(graph.g)
    stats = graph.stats()

    # 跨域查询结果
    q1 = pt.semantic_ask("华东师大哪些老师研究知识图谱")
    q2 = pt.semantic_ask("哪些公司在人工智能行业")
    q3 = pt.semantic_ask("哪些公司在物流行业")
    q4 = pt.semantic_ask("大语言模型领域近几年趋势如何")
    q5 = pt.semantic_ask("哪些机构在可信数据空间产出最多")

    # 本体性转化示例：取一条公司原始行 -> 三元组
    sample = pt.entity_detail("c_C001")

    # 生成 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>面向 AI 智能体的大数据平台 · 原型</title>
<style>
  :root {{ --fg:var(--foreground,#1a1a1a); --mut:var(--muted-foreground,#666);
    --accent:var(--accent,#2f6fed); --border:var(--border,#e5e5e5); --card:var(--card,#fff); }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; color:var(--fg); margin:0; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:28px 20px 48px; }}
  h1 {{ font-size:24px; margin:0 0 6px; }}
  .sub {{ color:var(--mut); font-size:14px; margin:0 0 22px; }}
  .layers {{ display:flex; flex-direction:column; gap:8px; margin:16px 0 26px; }}
  .layer {{ display:flex; gap:12px; border:1px solid var(--border); border-radius:10px; padding:12px 14px; background:var(--card); align-items:center; }}
  .layer b {{ min-width:110px; color:var(--accent); font-size:14px; }}
  .layer span {{ font-size:12px; color:var(--mut); line-height:1.5; }}
  .card {{ border:1px solid var(--border); border-radius:12px; padding:18px; margin-bottom:16px; background:var(--card); }}
  .q {{ font-weight:600; font-size:15px; margin-bottom:10px; }}
  .bar-row {{ display:flex; align-items:center; gap:8px; margin:5px 0; }}
  .bar-label {{ width:230px; font-size:12px; text-align:right; color:var(--mut); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .bar-track {{ flex:1; height:13px; background:rgba(0,0,0,0.05); border-radius:6px; overflow:hidden; }}
  .bar-fill {{ display:block; height:100%; background:var(--accent); border-radius:6px; }}
  .bar-val {{ width:55px; font-size:12px; }}
  .trend-wrap {{ display:flex; align-items:flex-end; gap:10px; height:165px; padding:10px 4px 0; }}
  .trend-col {{ display:flex; flex-direction:column; align-items:center; gap:4px; }}
  .trend-bar {{ width:44px; background:var(--accent); border-radius:4px 4px 0 0; }}
  .trend-year {{ font-size:12px; color:var(--mut); }} .trend-val {{ font-size:12px; font-weight:600; }}
  .triple {{ font-family:ui-monospace,Consolas,monospace; font-size:12px; background:rgba(0,0,0,0.04); border-radius:6px; padding:8px 10px; margin:4px 0; overflow-x:auto; white-space:nowrap; }}
  .mcp {{ display:flex; gap:8px; flex-wrap:wrap; margin:10px 0; }}
  .tool {{ border:1px solid var(--border); border-radius:8px; padding:6px 10px; font-size:12px; background:var(--card); }}
  h3 {{ margin:24px 0 10px; font-size:16px; }}
  .evolve {{ display:flex; gap:8px; margin:12px 0; flex-wrap:wrap; }}
  .ev {{ flex:1; min-width:120px; border:1px solid var(--border); border-radius:8px; padding:10px; font-size:12px; }}
  .ev b {{ display:block; color:var(--accent); margin-bottom:4px; }}
  .foot {{ color:var(--mut); font-size:12px; margin-top:22px; }}
  .two-col {{ display:flex; gap:18px; flex-wrap:wrap; }}
  .two-col>div {{ flex:1; min-width:280px; }}
</style></head><body><div class="wrap">
<h1>🧠 面向 AI 智能体的大数据平台</h1>
<p class="sub">本体（Ontology）作语义契约 · 异构数据「本体性转化」成统一知识图谱 · MCP 让任何 AI 都能接入</p>

<div class="layers">
  <div class="layer"><b>① 数据接入层</b><span>注册任意数据源（CSV/JSON/Parquet/SQL），自动检测 schema —— 已接入 {len(cat.list())} 个源：学术（学者/论文/机构/领域）+ 企业（公司/行业）</span></div>
  <div class="layer"><b>② 本体语义层</b><span>OWL 本体（{len(onto.classes)} 类 / {len(onto.object_props)} 关系）+ 语义映射，把原始行「转化」成 RDF 三元组 —— 统一图 {stats['triples']} 三元组 / {stats['entities']} 实体</span></div>
  <div class="layer"><b>③ 工具接口层</b><span>从本体生成 8 个工具（Function Calling），数据能力变成 AI 可调的接口</span></div>
  <div class="layer"><b>④ AI 网关层</b><span>MCP（Model Context Protocol）暴露全部工具 —— Claude / GPT / Cursor / 任意 Agent 都能连</span></div>
</div>

<h3>本体性转化：原始数据行 → 本体三元组</h3>
<div class="card">
  <div class="q">上市公司 CSV 一行</div>
  <div class="triple">C001,阿里巴巴,电商,杭州,9411.68,204891,1999</div>
  <div class="q" style="margin-top:12px">转化成本体三元组（Company / belongsToIndustry / revenue…）</div>
  <div class="triple">&lt;res:c_C001&gt; a onto:Company ; onto:name "阿里巴巴" ; onto:belongsToIndustry &lt;res:ind_电商&gt; ; onto:revenue 9411.68 ; onto:region "杭州"</div>
  <p style="color:var(--mut);font-size:12px">同样的映射引擎也把 OpenAlex 学术数据转化进同一张图 —— 这就是「本体性转化」：异构数据 → 统一语义模型。</p>
</div>

<h3>跨域语义查询（同一平台，学术 + 企业）</h3>
<div class="two-col">
  <div class="card"><div class="q">Q1 华东师大哪些老师研究知识图谱？</div>{_scholar_bars(q1)}</div>
  <div class="card"><div class="q">Q2 哪些公司在人工智能行业？</div>{bars(q2.get("companies",[]), "name", "revenue_b", "亿")}</div>
</div>
<div class="two-col">
  <div class="card"><div class="q">Q3 哪些公司在物流行业？</div>{bars(q3.get("companies",[]), "name", "revenue_b", "亿")}</div>
  <div class="card"><div class="q">Q4 大语言模型领域论文趋势</div>{trend(q4.get("trend",[]))}</div>
</div>

<h3>本体消歧（跨语言标签 → 实体）</h3>
<div class="card">
  <div class="triple">"知识图谱" → res:f_C2987255567 · "deep learning" → res:f_C108583219 · "华东师大" → res:i_I66867065</div>
  <p style="color:var(--mut);font-size:12px">LLM 只懂字符串，本体的中英文标签让它把词「锚定」到唯一实体，消除歧义 —— 这正是本体论作为「语义层关键答案」的依据。</p>
</div>

<h3>AI 网关：MCP 暴露 8 个工具（任何 AI 都能连）</h3>
<div class="card">
  <div class="mcp">
    <span class="tool">list_ontology</span><span class="tool">list_sources</span><span class="tool">explore_class</span>
    <span class="tool">find_entity</span><span class="tool">entity_detail</span><span class="tool">query_relation</span>
    <span class="tool">sparql</span><span class="tool">semantic_ask</span>
  </div>
  <p style="color:var(--mut);font-size:12px">Claude / GPT / Gemini / Cursor 用同一份 mcp_config.json 即可接入，无需改动平台任何代码 —— AI 无关。</p>
</div>

<h3>传统平台 → AI 平台的演进路径</h3>
<div class="evolve">
  <div class="ev"><b>L0 传统</b>数据库+BI+报表</div>
  <div class="ev"><b>L1 语义增强</b>本体+知识图谱</div>
  <div class="ev"><b>L2 接口工具化</b>数据封装成 API</div>
  <div class="ev"><b>L3 AI 原生</b>MCP 接入任何 AI</div>
  <div class="ev"><b>L4 AI-native</b>自治数据运营</div>
</div>

<p class="foot">数据：OpenAlex（学术）+ 模拟企业数据（合规公开/模拟）· 本体：OWL（owlready2）· 图：RDF（rdflib）· 接入：MCP</p>
</div></body></html>"""

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "showcase.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"展示页已生成: {out}")

def _scholar_bars(q):
    names = q.get("scholars", [])[:10]
    items = [{"name": n, "papers": 1} for n in names]
    return bars(items, "name", "papers", "")

if __name__ == "__main__":
    main()
