# -*- coding: utf-8 -*-
"""
扩充数据抓取 v2：
- 扩机构（10 所，含物流/供应链相关）
- 扩领域（10 个，覆盖 AI 大数据平台相关）
- 扩论文（每领域更多页）
- 新增：物流/供应链企业域（贴合赛题场景）
- 新增：开放数据集元数据（Dataset 实体）
"""
import json, time, os, sys
import requests

BASE = "https://api.openalex.org"
MAILTO = "team@ecnu.edu.cn"
RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
os.makedirs(RAW, exist_ok=True)
S = requests.Session()
S.headers.update({"User-Agent": f"mailto:{MAILTO}"})

def get(url, params=None):
    p = dict(params or {}); p["mailto"] = MAILTO
    r = S.get(url, params=p, timeout=60)
    r.raise_for_status()
    return r.json()

def save(name, data):
    with open(os.path.join(RAW, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"  保存 {name}: {len(data) if isinstance(data, (list, dict)) else '?'}")

def paged(url, params, max_pages=3, per_page=100, sleep=0.25):
    out, cursor = [], "*"
    for _ in range(max_pages):
        p = dict(params); p.update({"per-page": per_page, "cursor": cursor, "mailto": MAILTO})
        d = get(url, p)
        out.extend(d.get("results", []))
        cursor = d.get("meta", {}).get("next_cursor")
        if not cursor: break
        time.sleep(sleep)
    return out

INSTITUTIONS = [
    ("East China Normal University", "华东师范大学"),
    ("Shanghai Jiao Tong University", "上海交通大学"),
    ("Fudan University", "复旦大学"),
    ("Tsinghua University", "清华大学"),
    ("Zhejiang University", "浙江大学"),
    ("Peking University", "北京大学"),
    ("Shanghai University", "上海大学"),
    ("Tongji University", "同济大学"),
    ("Shanghai Maritime University", "上海海事大学"),
    ("Beijing University of Posts and Telecommunications", "北京邮电大学"),
    ("Huazhong University of Science and Technology", "华中科技大学"),
    ("University of Science and Technology of China", "中国科学技术大学"),
]

TOPICS = [
    ("知识图谱", "knowledge graph", "C2987255567"),
    ("深度学习", "deep learning", "C108583219"),
    ("数据挖掘", "data mining", "C124101348"),
    ("大语言模型", "large language model", None),
    ("可信数据空间", "trusted data space", None),
    ("联邦学习", "federated learning", None),
    ("知识蒸馏", "knowledge distillation", None),
    ("图神经网络", "graph neural network", None),
    ("语义网", "semantic web", None),
    ("数据治理", "data governance", None),
    ("供应链管理", "supply chain management", None),
    ("物流优化", "logistics optimization", None),
]

def main():
    print("== 1. 机构 ==")
    insts = []
    for en, cn in INSTITUTIONS:
        try:
            d = get(f"{BASE}/institutions", {"search": en, "per-page": 1})
            if d.get("results"):
                i = d["results"][0]
                insts.append({"openalex_id": i["id"], "name": i["display_name"], "cn_name": cn,
                              "country": i.get("country_code"), "works_count": i.get("works_count"),
                              "cited_by_count": i.get("cited_by_count"),
                              "h_index": i.get("summary_stats", {}).get("h_index"),
                              "region": i.get("geo", {}).get("city")})
                print(f"  {cn} ({i['display_name']}) works={i.get('works_count')}")
        except Exception as e:
            print(f"  {cn} 失败 {e}")
        time.sleep(0.2)
    save("v2_institutions.json", insts)

    print("\n== 2. 概念 ==")
    concepts = []
    topic_ids = {}
    for cn, en, cid in TOPICS:
        if cid is None:
            # 用概念搜索
            try:
                d = get(f"{BASE}/concepts", {"search": en, "per-page": 1})
                if d.get("results"):
                    c = d["results"][0]
                    cid = c["id"].split("/")[-1]
            except Exception:
                pass
        if cid:
            topic_ids[cn] = {"id": cid, "en": en}
        concepts.append({"cn_label": cn, "en_query": en, "openalex_id": cid})
    save("v2_concepts.json", concepts)
    print(f"  成功映射 {len(topic_ids)}/{len(TOPICS)} 个概念")

    print("\n== 3. 论文（多领域 × 多机构）==")
    inst_ids = "|".join(i["openalex_id"].split("/")[-1] for i in insts)
    works_by_topic = {}
    for cn, meta in topic_ids.items():
        cid = meta["id"]
        try:
            ws = paged(f"{BASE}/works",
                       {"filter": f"concepts.id:{cid},institutions.id:{inst_ids}"},
                       max_pages=3, per_page=100)
            if len(ws) < 30:
                ws2 = paged(f"{BASE}/works", {"filter": f"concepts.id:{cid}"}, max_pages=3, per_page=100)
                seen = {w["id"] for w in ws}
                ws += [w for w in ws2 if w["id"] not in seen]
            works_by_topic[cn] = ws
            print(f"  {cn}: {len(ws)} 篇")
        except Exception as e:
            print(f"  {cn} 失败: {e}")
        time.sleep(0.3)
    save("v2_works_by_topic.json", works_by_topic)

    all_works = {}
    for ws in works_by_topic.values():
        for w in ws:
            all_works[w["id"]] = w
    save("v2_works_all.json", list(all_works.values()))
    print(f"  去重后 {len(all_works)} 篇论文")

    print("\n== 4. 物流/供应链企业 ==")
    # 公开上市公司信息（模拟/公开合规数据）
    companies = [
        # 物流快递
        ("顺丰控股", "物流快递", "深圳", 2584.09, 162000), ("中通快递", "物流快递", "上海", 384.19, 24000),
        ("圆通速递", "物流快递", "上海", 576.84, 17000), ("韵达股份", "物流快递", "上海", 449.83, 13000),
        ("申通快递", "物流快递", "上海", 409.24, 12000), ("京东物流", "物流快递", "北京", 1666.10, 430000),
        ("德邦股份", "物流快递", "上海", 369.16, 68000), ("菜鸟网络", "物流快递", "杭州", 990.20, 14000),
        # 航运港口
        ("中远海控", "航运物流", "上海", 1754.48, 31232), ("招商轮船", "航运物流", "上海", 258.83, 4769),
        ("宁波港", "港口物流", "宁波", 257.04, 16790), ("上港集团", "港口物流", "上海", 372.86, 12000),
        ("青岛港", "港口物流", "青岛", 181.67, 11000), ("广州港", "港口物流", "广州", 131.94, 9000),
        ("上海机场", "航空物流", "上海", 110.47, 10472), ("白云机场", "航空物流", "广州", 68.35, 8000),
        # 供应链/货运
        ("中国外运", "供应链", "北京", 1084.65, 34000), ("怡亚通", "供应链", "深圳", 798.29, 11000),
        ("密尔克卫", "供应链", "上海", 121.63, 4000), ("海晨股份", "供应链", "苏州", 18.65, 2500),
        # 电商（含物流）
        ("阿里巴巴", "电商", "杭州", 9411.68, 204891), ("京东", "电商", "北京", 10462.36, 517000),
        ("拼多多", "电商", "上海", 2476.39, 17403), ("美团", "本地生活", "北京", 2767.00, 114554),
        # AI 相关
        ("科大讯飞", "人工智能", "合肥", 196.50, 14878), ("商汤科技", "人工智能", "上海", 34.06, 4062),
        ("百度", "人工智能", "北京", 1345.98, 39800), ("腾讯", "互联网", "深圳", 6090.15, 108436),
        ("华为", "通信设备", "深圳", 7041.74, 207000), ("中芯国际", "芯片", "上海", 452.50, 21619),
        ("寒武纪", "芯片", "北京", 11.79, 1373), ("澜起科技", "芯片", "上海", 22.86, 700),
        ("比亚迪", "新能源汽车", "深圳", 6023.15, 703504), ("宁德时代", "新能源电池", "宁德", 4009.17, 118068),
        ("隆基绿能", "光伏", "西安", 1294.98, 52465), ("三一重工", "工程机械", "长沙", 740.19, 25539),
        ("中国中车", "轨道交通", "北京", 2342.62, 162731), ("中国移动", "通信运营", "北京", 10093.00, 451830),
        ("工商银行", "金融", "北京", 8430.70, 419252), ("招商银行", "金融", "深圳", 3391.23, 116529),
        ("中国平安", "金融", "深圳", 10318.63, 288751), ("贵州茅台", "消费品", "遵义", 1505.60, 30060),
        ("海尔智家", "家电", "青岛", 2614.28, 109586), ("美的集团", "家电", "佛山", 3737.10, 166243),
    ]
    save("v2_companies.json", [
        {"company_id": f"C{i+1:03d}", "name": n, "industry": ind, "region": reg,
         "revenue_b": rev, "employees": emp, "founded": None}
        for i, (n, ind, reg, rev, emp) in enumerate(companies)
    ])
    print(f"  {len(companies)} 家企业")

    print("\n== 5. 开放数据集元数据 ==")
    datasets = [
        {"dataset_id": "D001", "name": "OpenAlex 学术知识图谱", "field": "知识图谱", "size": "2.5亿+ 论文记录", "license": "CC0", "url": "https://openalex.org"},
        {"dataset_id": "D002", "name": "arXiv 全文语料", "field": "大语言模型", "size": "240万+ 论文", "license": "CC0", "url": "https://arxiv.org"},
        {"dataset_id": "D003", "name": "Crossref 元数据", "field": "数据治理", "size": "1.5亿+ DOI", "license": "开放", "url": "https://crossref.org"},
        {"dataset_id": "D004", "name": "DBLP 计算机文献库", "field": "数据挖掘", "size": "700万+ 条目", "license": "开放", "url": "https://dblp.org"},
        {"dataset_id": "D005", "name": "中国上市公司年报数据", "field": "供应链管理", "size": "5000+ 公司", "license": "公开披露", "url": "-"},
    ]
    save("v2_datasets.json", datasets)
    print(f"  {len(datasets)} 个数据集")

    print("\n完成。")

if __name__ == "__main__":
    main()
