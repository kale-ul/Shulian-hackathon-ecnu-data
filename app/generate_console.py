# -*- coding: utf-8 -*-
"""
生成静态控制台（路演/内嵌预览用）
用真实的 6 个 AI × 多个问题，生成可点击切换的完整界面
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiplatform.build_platform import build
from aiplatform.ai_clients import list_clients, call_client
from aiplatform.semantic import GenericSemanticQuery
from aiplatform.upload import ingest_file
import html as _html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
onto, cat, graph = build()
gq = GenericSemanticQuery(graph.g)

QUESTIONS = [
    ("华东师范大学有哪些学者？", "学者"),
    ("大语言模型趋势", "趋势"),
    ("物流快递行业有哪些公司？", "企业"),
    ("哪个机构论文最多？", "排名"),
    ("知识图谱领域有哪些论文？", "领域"),
]

# 选用能真实调用的 AI（http + cli），本地兜底也放一个
ALL = list_clients()
print("可用 AI：", [c["name"] for c in ALL])

# 平台自身端点和本地兜底不需要外部调用，但也要出现在列表里展示
results = []   # [{ai, ai_key, q, tag, intent, answer, backend, ms, data}]
for c in ALL:
    for q, tag in QUESTIONS[:5]:     # 每个 AI 跑 4 个问题，控制耗时
        r = gq.ask(q)
        data_rows = []
        if "companies" in r:
            data_rows = [["公司名称", "所属行业"], *[[x.get("name"), r.get("industry")] for x in r["companies"][:20]]]
        elif "scholars" in r:
            data_rows = [["序号", "学者"], *[[i + 1, x] for i, x in enumerate(r["scholars"][:20])]]
        elif "entities" in r:
            data_rows = [["序号", "实体"], *[[i + 1, x] for i, x in enumerate(r["entities"][:20])]]
        elif "samples" in r:
            data_rows = [["序号", "实体"],
                         *[[i + 1, (x.get("name") if isinstance(x, dict) else x)] for i, x in enumerate(r["samples"][:20])]]
        elif r.get("intent") == "trend" and r.get("data"):
            data_rows = [["年份", "论文数"], *[[x["name"], x["count"]] for x in r["data"]]]
        elif r.get("intent") == "entity_detail":
            data_rows = [["属性", "值"], *[[k, v] for k, v in (r.get("properties") or {}).items()]]
        elif "data" in r and isinstance(r["data"], list) and r["data"]:
            k0 = r["data"][0]
            if "count" in k0:
                data_rows = [["名称", "数量"], *[[x["name"], x["count"]] for x in r["data"][:15]]]
            elif "value" in k0:
                data_rows = [["名称", "数值"], *[[x["name"], x["value"]] for x in r["data"][:15]]]
        elif "classes" in r:
            data_rows = [["本体类", "实例数"], *[[k, v] for k, v in r["classes"].items()]]

        if c["kind"] == "local":
            ans = f"（本地引擎）识别意图 **{r.get('intent')}**，返回 {max(len(data_rows)-1,0)} 条结构化结果。"
            backend, ms = "rule-based", 0
        else:
            try:
                resp = call_client(c["key"], [
                    {"role": "system", "content": "你是数据平台助手。根据查询结果用简洁中文回答，可列点，不要编造。"},
                    {"role": "user", "content": f"问题：{q}\n\n平台查询结果：{json.dumps(r, ensure_ascii=False)}"},
                ], timeout=180)
                ans = resp.get("content") or f"（未返回：{resp.get('error')}）"
                backend, ms = resp.get("backend"), resp.get("elapsed_ms")
            except Exception as e:
                ans, backend, ms = f"（调用失败：{e}）", None, None
        print(f"  ✓ {c['name']} | {q} | {r.get('intent')} | {str(ms)}ms | {str(ans)[:50]}")
        results.append({"ai": c["name"], "ai_key": c["key"], "q": q, "tag": tag,
                        "intent": r.get("intent"), "answer": ans, "backend": backend, "ms": ms,
                        "rows": data_rows, "raw": json.dumps(r, ensure_ascii=False)[:800]})

stats = graph.stats()
d = onto.describe()
clients_meta = [{"name": c["name"], "kind": c["kind"], "model": c["model"], "note": c["note"]} for c in ALL]
sources = [{"name": s["name"], "kind": s["kind"], "rows": s["rows"]} for s in cat.list()]

payload = {
    "stats": {"sources": len(sources), "triples": stats["triples"], "entities": stats["entities"],
              "classes": stats["classes"]},
    "ontology": d,
    "clients": clients_meta,
    "sources": sources,
    "results": results,
}
out_json = os.path.join(BASE, "app", "console_data.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=1)
print(f"\n数据已写出：{out_json}（{len(results)} 组真实结果）")
