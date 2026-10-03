# -*- coding: utf-8 -*-
"""
OpenAlex 数据抓取脚本
围绕 demo 主题拉取：机构 / 概念 / 论文 / 学者
输出到 data/raw/*.json
"""
import json, time, os, sys
import requests

BASE = "https://api.openalex.org"
MAILTO = "team@ecnu.edu.cn"
RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(RAW, exist_ok=True)

S = requests.Session()
S.headers.update({"User-Agent": f"mailto:{MAILTO}"})

def get(url, params=None):
    params = dict(params or {})
    params["mailto"] = MAILTO
    r = S.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def save(name, data):
    p = os.path.join(RAW, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"  保存 {name}")

def paged(url, params, max_pages=3, per_page=100):
    """翻页抓取，返回所有 results"""
    out = []
    cursor = "*"
    for i in range(max_pages):
        params = dict(params)
        params.update({"per-page": per_page, "cursor": cursor, "mailto": MAILTO})
        d = get(url, params)
        out.extend(d.get("results", []))
        cursor = d.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.3)
    return out

def main():
    # ============ 1. 机构 ============
    print("== 抓取机构 ==")
    inst_names = [
        "East China Normal University",
        "Shanghai Jiao Tong University",
        "Fudan University",
        "Tsinghua University",
        "Zhejiang University",
    ]
    institutions = []
    for name in inst_names:
        d = get(f"{BASE}/institutions", {"search": name, "per-page": 1})
        if d.get("results"):
            inst = d["results"][0]
            institutions.append({
                "openalex_id": inst["id"],
                "name": inst["display_name"],
                "country": inst.get("country_code"),
                "works_count": inst.get("works_count"),
                "cited_by_count": inst.get("cited_by_count"),
                "h_index": inst.get("summary_stats", {}).get("h_index"),
                "homepage": inst.get("homepage_url"),
            })
            print(f"  {inst['display_name']} -> {inst['id']} (works={inst.get('works_count')})")
        time.sleep(0.3)
    save("institutions.json", institutions)

    # ============ 2. 概念（领域） ============
    print("== 抓取概念 ==")
    topic_queries = [
        ("可信数据空间", "trusted data space"),
        ("大语言模型", "large language model"),
        ("知识图谱", "knowledge graph"),
        ("深度学习", "deep learning"),
        ("数据挖掘", "data mining"),
    ]
    concepts = []
    for cn_label, en_query in topic_queries:
        d = get(f"{BASE}/concepts", {"search": en_query, "per-page": 3})
        for c in d.get("results", [])[:3]:
            concepts.append({
                "openalex_id": c["id"],
                "name": c["display_name"],
                "cn_label": cn_label,
                "level": c.get("level"),
                "works_count": c.get("works_count"),
                "description": (c.get("description") or "")[:200],
            })
        time.sleep(0.3)
    save("concepts.json", concepts)
    print(f"  共 {len(concepts)} 个概念")

    # ============ 3. 论文（按概念抓取） ============
    print("== 抓取论文 ==")
    inst_ids = [i["openalex_id"] for i in institutions]
    # 概念 ID -> 简称，用于过滤
    concept_map = {}
    for c in concepts:
        cid = c["openalex_id"].split("/")[-1]
        if c["cn_label"] not in concept_map:
            concept_map[c["cn_label"]] = cid

    all_works = {}
    for cn_label, cid in concept_map.items():
        # 抓该概念下、这几所机构内的论文
        try:
            works = paged(
                f"{BASE}/works",
                {"filter": f"concepts.id:{cid},institutions.id:{'|'.join(x.split('/')[-1] for x in inst_ids)}"},
                max_pages=2, per_page=100,
            )
            # 补充：若结果太少，放宽到只按概念抓
            if len(works) < 10:
                works = paged(
                    f"{BASE}/works",
                    {"filter": f"concepts.id:{cid}"},
                    max_pages=2, per_page=100,
                )
            all_works[cn_label] = works
            print(f"  {cn_label}: {len(works)} 篇")
        except Exception as e:
            print(f"  {cn_label}: 抓取失败 {e}")
        time.sleep(0.3)
    save("works_by_concept.json", all_works)

    # 汇总所有论文 + 去重
    works_flat = {}
    for cn, ws in all_works.items():
        for w in ws:
            works_flat[w["id"]] = w
    save("works_all.json", list(works_flat.values()))
    print(f"  去重后共 {len(works_flat)} 篇论文")

    # ============ 4. 学者（从论文作者提取） ============
    print("== 抓取学者 ==")
    author_ids = set()
    for w in works_flat.values():
        for a in w.get("authorships", []):
            aid = a.get("author", {}).get("id")
            if aid:
                author_ids.add(aid)
    print(f"  涉及 {len(author_ids)} 位学者")

    authors = []
    author_ids = list(author_ids)[:120]  # 限制数量，控制抓取时间
    for i, aid in enumerate(author_ids):
        try:
            d = get(aid)
            authors.append({
                "openalex_id": aid,
                "name": d.get("display_name"),
                "works_count": d.get("works_count"),
                "cited_by_count": d.get("cited_by_count"),
                "h_index": d.get("summary_stats", {}).get("h_index"),
                "institution": (d.get("last_known_institutions") or [{}])[0].get("display_name") if d.get("last_known_institutions") else None,
                "institution_id": (d.get("last_known_institutions") or [{}])[0].get("id") if d.get("last_known_institutions") else None,
            })
        except Exception as e:
            print(f"  学者 {aid} 失败: {e}")
        if i % 10 == 0:
            print(f"  ...{i}/{len(author_ids)}")
        time.sleep(0.2)
    save("authors.json", authors)
    print(f"  成功 {len(authors)} 位学者")

    print("\n全部完成。")

if __name__ == "__main__":
    main()
