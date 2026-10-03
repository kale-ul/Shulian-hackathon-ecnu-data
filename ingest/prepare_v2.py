# -*- coding: utf-8 -*-
"""
把 v2 抓取的扩充数据接进平台（多机构 / 多领域 / 2438 论文 / 44 企业 / 数据集元数据）
产出标准 raw 文件，供 build_platform 统一转化
"""
import json, os
from pathlib import Path

BASE = Path(__file__).parent
RAW = BASE.parent / "data" / "raw"

def load(n):
    p = RAW / n
    if not p.exists():
        print(f"缺少 {n}"); return None
    return json.loads(p.read_text(encoding="utf-8"))

insts = load("v2_institutions.json") or []
concepts = load("v2_concepts.json") or []
works = load("v2_works_all.json") or []
companies = load("v2_companies.json") or []
datasets = load("v2_datasets.json") or []

print(f"读入：{len(insts)} 机构 / {len(concepts)} 概念 / {len(works)} 论文 / {len(companies)} 企业 / {len(datasets)} 数据集")

# ---------- 1. 机构 ----------
out_i = []
for i in insts:
    out_i.append({
        "institution_id": i["openalex_id"].split("/")[-1],
        "name": i["name"],
        "cn_name": i.get("cn_name"),
        "region": i.get("region"),
        "country": i.get("country"),
        "works_count": i.get("works_count"),
        "cited_by_count": i.get("cited_by_count"),
        "h_index": i.get("h_index"),
    })
(RAW / "v2_inst_clean.json").write_text(json.dumps(out_i, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"机构 -> v2_inst_clean.json ({len(out_i)})")

# ---------- 2. 领域 ----------
out_c = []
for c in concepts:
    if c.get("openalex_id"):
        out_c.append({"field_id": c["openalex_id"], "name": c["en_query"], "cn_name": c["cn_label"]})
(RAW / "v2_fields_clean.json").write_text(json.dumps(out_c, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"领域 -> v2_fields_clean.json ({len(out_c)})")

# ---------- 3. 论文 ----------
# 领域归属用「抓取主题」这个规范维度（而非 OpenAlex 的原始 concepts，那有 1291 个且噪声大）
topic_of_work = {}
wt = load("v2_works_by_topic.json") or {}
for topic_cn, ws in wt.items():
    for w in ws:
        topic_of_work.setdefault(w["id"], set()).add(topic_cn)

out_w = []
for w in works:
    try:
        wid = w["id"]
        out_w.append({
            "work_id": wid.split("/")[-1],
            "title": (w.get("title") or w.get("display_name") or "")[:300],
            "year": w.get("publication_year"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "cited_by_count": w.get("cited_by_count", 0),
            "type": w.get("type"),
            "domain": sorted(topic_of_work.get(wid, [])) or ["其他"],
            "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])[:10]],
            "author_ids": [a["author"]["id"].split("/")[-1] for a in (w.get("authorships") or [])[:10]],
            "institutions": list({i["display_name"] for a in (w.get("authorships") or [])
                                  for i in (a.get("institutions") or [])})[:5],
            "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
        })
    except Exception:
        pass
(RAW / "v2_works_clean.json").write_text(json.dumps(out_w, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"论文 -> v2_works_clean.json ({len(out_w)})，每篇带规范领域标签")

# ---------- 4. 企业 ----------
# 注意：v2 企业 id 加 V2 前缀，避免与 v1 的 C001.. 冲突（两表内容不同）
(RAW / "companies_v2.csv").write_text(
    "company_id,name,industry,region,revenue_b,employees\n" +
    "\n".join(f'V2{c["company_id"]},{c["name"]},{c["industry"]},{c["region"]},{c["revenue_b"]},{c["employees"]}'
              for c in companies), encoding="utf-8")
print(f"企业 -> companies_v2.csv ({len(companies)})")

# ---------- 5. 数据集 ----------
(RAW / "datasets.csv").write_text(
    "dataset_id,name,field,size,license,url\n" +
    "\n".join(f'{d["dataset_id"]},{d["name"]},{d["field"]},{d["size"]},{d["license"]},{d["url"]}'
              for d in datasets), encoding="utf-8")
print(f"数据集 -> datasets.csv ({len(datasets)})")

print("\n完成。")
