# -*- coding: utf-8 -*-
"""把 console_data.json 渲染成可点击的静态控制台 HTML（路演/内嵌预览）"""
import os, json, html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = json.load(open(os.path.join(BASE, "app", "console_data.json"), encoding="utf-8"))
st_, onto_, clients, sources, results = (data["stats"], data["ontology"], data["clients"],
                                         data["sources"], data["results"])

TAGCOLOR = {"http": "#0ea5e9", "cli": "#8b5cf6", "local": "#64748b", "platform": "#059669"}
TAGNAME = {"http": "云端 API", "cli": "本地 Agent", "local": "兜底引擎", "platform": "平台自身"}

ai_cards = "".join(
    f'<button class="aibtn" data-ai="{html.escape(c["name"])}" '
    f'style="border-left:3px solid {TAGCOLOR[c["kind"]]}">'
    f'<span class="ainame">{html.escape(c["name"])}</span>'
    f'<span class="aitag" style="background:{TAGCOLOR[c["kind"]]}1a;color:{TAGCOLOR[c["kind"]]}">'
    f'{TAGNAME[c["kind"]]}</span>'
    f'<span class="aimodel">{html.escape(c["model"])}</span></button>'
    for c in clients)

src_rows = "".join(
    f'<tr><td>{html.escape(s["name"])}</td><td>{s["kind"]}</td><td class="num">{s["rows"]}</td></tr>'
    for s in sources[:40])

cls_rows = "".join(f'<tr><td>{html.escape(k)}</td><td class="num">{v}</td></tr>'
                   for k, v in sorted(st_[ "classes"].items(), key=lambda x: -x[1]))

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>面向 AI 的大数据平台 · 控制台</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;font-family:var(--app-font,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif);
color:var(--foreground,#1e293b);background:transparent;font-size:13px}}
.wrap{{display:grid;grid-template-columns:210px 1fr 300px;gap:12px;padding:12px;min-height:560px}}
.panel{{border:1px solid var(--border,#e2e8f0);border-radius:10px;padding:10px;background:var(--card,#fff)}}
h3{{margin:0 0 8px;font-size:13px;font-weight:650}}
.muted{{color:var(--muted-foreground,#64748b);font-size:11px;line-height:1.5}}
.aibtn{{display:grid;grid-template-columns:1fr auto;gap:1px 6px;width:100%;text-align:left;
padding:6px 8px;margin-bottom:4px;border:1px solid var(--border,#e2e8f0);border-radius:7px;
background:transparent;cursor:pointer;font-family:inherit;color:inherit;transition:.12s}}
.aibtn:hover{{background:var(--accent,#f1f5f9)}}
.aibtn.on{{background:var(--accent,#f1f5f9);border-color:#0ea5e9}}
.ainame{{font-size:12px;font-weight:600}}
.aitag{{font-size:9px;padding:1px 5px;border-radius:99px;justify-self:end;align-self:center}}
.aimodel{{grid-column:1/-1;font-size:10px;color:var(--muted-foreground,#64748b)}}
.kv{{display:flex;justify-content:space-between;padding:3px 0;font-size:11px;border-bottom:1px dashed var(--border,#e2e8f0)}}
.kv b{{font-variant-numeric:tabular-nums}}
.demos{{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0}}
.demo{{font-size:11px;padding:3px 9px;border:1px solid var(--border,#e2e8f0);border-radius:99px;
background:transparent;cursor:pointer;font-family:inherit;color:inherit}}
.demo:hover{{background:var(--accent,#f1f5f9)}}
.demo.on{{background:#0ea5e9;color:#fff;border-color:#0ea5e9}}
.bubble{{padding:8px 11px;border-radius:9px;margin:6px 0;line-height:1.65;white-space:pre-wrap}}
.user{{background:#0ea5e9;color:#fff;margin-left:18%}}
.ai-ans{{background:var(--accent,#f1f5f9);border:1px solid var(--border,#e2e8f0)}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th,td{{padding:3px 5px;text-align:left;border-bottom:1px solid var(--border,#e2e8f0)}}
th{{color:var(--muted-foreground,#64748b);font-weight:600}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.bar{{height:7px;background:#0ea5e9;border-radius:2px;display:inline-block;vertical-align:middle}}
.chip{{display:inline-block;font-size:10px;padding:1px 6px;border-radius:99px;
background:var(--accent,#f1f5f9);border:1px solid var(--border,#e2e8f0);margin:1px 2px 1px 0}}
.scroll{{max-height:300px;overflow:auto}}
</style></head><body>
<div class="wrap">

<div class="panel">
  <h3>🧠 平台</h3>
  <div class="kv"><span>数据源</span><b>{st_["sources"]}</b></div>
  <div class="kv"><span>本体三元组</span><b>{st_["triples"]:,}</b></div>
  <div class="kv"><span>实体</span><b>{st_["entities"]:,}</b></div>
  <div class="kv"><span>本体类</span><b>{len(onto_["classes"])}</b></div>
  <div class="kv"><span>关系/属性</span><b>{len(onto_["object_properties"])}/{len(onto_["data_properties"])}</b></div>
  <h3 style="margin-top:12px">① 选择 AI（{len(clients)} 个）</h3>
  <div id="aila">{ai_cards}</div>
  <h3 style="margin-top:12px">数据源清单</h3>
  <div class="scroll"><table><tr><th>名称</th><th>类型</th><th class="num">行数</th></tr>{src_rows}</table></div>
</div>

<div class="panel">
  <h3>💬 对话（AI 实时调用平台数据）</h3>
  <div class="muted">当前 AI：<b id="curAI"></b> · 以下是真实调用结果，点按钮或问题即可切换</div>
  <div class="demos" id="qs"></div>
  <div id="chat" style="min-height:220px"></div>
  <div class="muted" style="margin-top:6px">上传任意 Excel / Word / PDF / 图片 → 自动推断语义映射 → 本体性转化 → AI 立即可查</div>
</div>

<div class="panel">
  <h3>🔗 调用链 &amp; 数据</h3>
  <div id="trace" class="muted">选择 AI 与问题后，这里显示完整调用链。</div>
  <h3 style="margin-top:10px">本体实例分布</h3>
  <div class="scroll"><table>{cls_rows}</table></div>
</div>

</div>
<script>
const DATA = {json.dumps(results, ensure_ascii=False)};
const CL = {json.dumps(clients, ensure_ascii=False)};
let curAI = DATA.length ? DATA[0].ai : "", curQ = DATA.length ? DATA[0].q : "";

function aiList(){{ return [...new Set(DATA.map(d=>d.ai))]; }}
function qList(ai){{ return DATA.filter(d=>d.ai===ai).map(d=>d.q); }}
function find(ai,q){{ return DATA.find(d=>d.ai===ai && d.q===q); }}

function renderQs(){{
  const box = document.getElementById('qs');
  const qs = [...new Set(DATA.map(d=>d.q))];
  const has = qs.filter(q=>find(curAI,q));
  box.innerHTML = has.map(q=>{{
    const tag = (find(curAI,q)||{{}}).tag || '';
    return `<button class="demo ${{q===curQ?'on':''}}" data-q="${{q}}">${{tag||q.slice(0,8)}}</button>`;
  }}).join('') + has.map(q=>'').join('');
}}

function render(){{
  document.getElementById('curAI').textContent = curAI;
  document.getElementById('curAI').nextSibling;
  renderQs();
  const d = find(curAI, curQ);
  const chat = document.getElementById('chat');
  const tr = document.getElementById('trace');
  if(!d){{ chat.innerHTML='<div class="muted">该 AI 不支持此问题。</div>'; tr.innerHTML='<div class="muted">无数据</div>'; return; }}
  chat.innerHTML = `<div class="bubble user">${{d.q}}</div>
    <div class="bubble ai-ans">${{d.answer.replace(/</g,'&lt;')}}</div>
    <div class="muted">${{d.ai}} · 意图 <code>${{d.intent}}</code>${{d.ms?` · ${{d.ms}}ms`:''}}</div>`;
  let rows = '';
  if(d.rows && d.rows.length>1){{
    const nums = d.rows.slice(1).map(r=>parseFloat(r[1])).filter(v=>!isNaN(v));
    const mx = nums.length ? Math.max(...nums) : 0;
    const c1 = d.rows[0][0], c2 = d.rows[0][1];
    rows = '<table><tr><th>'+c1+'</th><th class="num">'+c2+'</th></tr>'+
      d.rows.slice(1).map(r=>{{
        const v = parseFloat(r[1]);
        const bar = (!isNaN(v) && mx>0)
          ? ` <span class="bar" style="width:${{Math.max(2,Math.round(v/mx*80))}}px"></span>` : '';
        return `<tr><td>${{r[0]}}</td><td class="num">${{r[1]??''}}${{bar}}</td></tr>`;
      }}).join('')+'</table>';
  }}
  tr.innerHTML = `<div class="kv"><span>① 本体语义查询</span><b>${{d.intent}}</b></div>
    <div class="kv"><span>② AI 生成答案</span><b>${{d.backend||'rule-based'}}</b></div>
    <div class="kv"><span>耗时</span><b>${{d.ms?d.ms+'ms':'—'}}</b></div>
    <div style="margin-top:8px">${{rows}}</div>`;
}}

document.getElementById('aila').addEventListener('click', e=>{{
  const b = e.target.closest('.aibtn'); if(!b) return;
  curAI = b.dataset.ai;
  const qs = qList(curAI); if(!qs.includes(curQ)) curQ = qs[0];
  document.querySelectorAll('.aibtn').forEach(x=>x.classList.toggle('on', x.dataset.ai===curAI));
  render();
}});
document.getElementById('qs').addEventListener('click', e=>{{
  const b = e.target.closest('.demo'); if(!b) return;
  curQ = b.dataset.q; render();
}});

// 初始化
document.querySelectorAll('.aibtn').forEach(x=>x.classList.toggle('on', x.dataset.ai===curAI));
render();
</script>
</body></html>"""

out = os.path.join(BASE, "app", "static_console.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print("静态控制台已生成：", out)
print("AI 数:", len(clients), "| 结果组数:", len(results))
