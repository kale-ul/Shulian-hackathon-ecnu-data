# -*- coding: utf-8 -*-
"""
补充抓取：用标题/关键词检索补上「大语言模型」「可信数据空间」两个主题
（概念搜索对这两个词返回 0，改用 works 的 title/keyword 检索）
"""
import json, time, os
import requests

BASE = "https://api.openalex.org"
RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
S = requests.Session()
S.headers.update({"User-Agent": "mailto:team@ecnu.edu.cn"})

def get(url, params=None):
    params = dict(params or {})
    params["mailto"] = "team@ecnu.edu.cn"
    r = S.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def save(name, data):
    with open(os.path.join(RAW, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

def paged(url, params, max_pages=2, per_page=100):
    out, cursor = [], "*"
    for _ in range(max_pages):
        p = dict(params); p.update({"per-page": per_page, "cursor": cursor, "mailto": "team@ecnu.edu.cn"})
        d = get(url, p)
        out.extend(d.get("results", []))
        cursor = d.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.3)
    return out

def main():
    inst_ids = "|".join([
        "I66867065",  # ECNU
        "I183067930", # SJTU
        "I24943067",  # Fudan
        "I99065089",  # Tsinghua
        "I76130692",  # Zhejiang
    ])

    topics = {
        "大语言模型": "large language model",
        "可信数据空间": "trusted data space",
    }

    # 先尝试概念搜索找 LLM 的概念 ID（用于本体概念映射）
    print("== 概念诊断 ==")
    for q in ["language model", "large language models", "natural language processing"]:
        d = get(f"{BASE}/concepts", {"search": q, "per-page": 3})
        print(f"  concept [{q}]:")
        for c in d.get("results", []):
            print(f"    {c['display_name']} | {c['id'].split('/')[-1]} | works={c.get('works_count')}")
        time.sleep(0.3)

    new_works = {}
    for cn_label, en_query in topics.items():
        print(f"== 抓取 [{cn_label}] ==")
        # 优先 title 检索（限五所机构内）
        try:
            ws = paged(f"{BASE}/works",
                       {"filter": f"title.search:{en_query},institutions.id:{inst_ids}"},
                       max_pages=2, per_page=100)
            if len(ws) < 5:
                # 放宽：不限机构，只按 title 检索
                ws = paged(f"{BASE}/works",
                           {"filter": f"title.search:{en_query}"},
                           max_pages=2, per_page=100)
            new_works[cn_label] = ws
            print(f"  {cn_label}: {len(ws)} 篇")
        except Exception as e:
            print(f"  {cn_label} 失败: {e}")
        time.sleep(0.3)

    save("works_extra_by_topic.json", new_works)

    # 合并到已有数据
    wb = json.load(open(os.path.join(RAW, "works_by_concept.json"), encoding="utf-8"))
    for k, v in new_works.items():
        wb[k] = v
    save("works_by_concept.json", wb)

    works_flat = {}
    for ws in wb.values():
        for w in ws:
            works_flat[w["id"]] = w
    save("works_all.json", list(works_flat.values()))
    print(f"== 合并后论文总数: {len(works_flat)} ==")
    for k, v in wb.items():
        print(f"  {k}: {len(v)}")

if __name__ == "__main__":
    main()
