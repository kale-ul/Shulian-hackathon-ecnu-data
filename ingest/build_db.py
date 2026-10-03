# -*- coding: utf-8 -*-
"""
把 works_all.json 解析成结构化表，写入 DuckDB + CSV
表：institutions / scholars / publications / venues / fields / author_of / affiliation / published_in / belongs_to_field
"""
import json, os, csv
import duckdb

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROC = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
os.makedirs(PROC, exist_ok=True)

def load(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return json.load(f)

# 5 个主题 -> Field 实体（openalex 概念 id）
FIELD_MAP = {
    "知识图谱":    {"id": "C2987255567", "en": "Knowledge graph", "level": 2},
    "深度学习":    {"id": "C108583219",  "en": "Deep learning",   "level": 2},
    "数据挖掘":    {"id": "C124101348",  "en": "Data mining",     "level": 1},
    "大语言模型":  {"id": "C137293760",  "en": "Language model",  "level": 2},
    "可信数据空间": {"id": "C2988382989", "en": "Data space",      "level": 2},
}

def short(openalex_url):
    return openalex_url.split("/")[-1] if openalex_url else None

def main():
    works_by_topic = load("works_by_concept.json")
    works_all = load("works_all.json")
    institutions = load("institutions.json")

    # ===== 实体容器 =====
    inst_map = {}      # id -> row
    scholar_map = {}   # id -> row
    pub_map = {}       # id -> row
    venue_map = {}     # id -> row
    field_map = {}     # id -> row

    # 机构（来自 institutions.json）
    for i in institutions:
        iid = short(i["openalex_id"])
        inst_map[iid] = {
            "openalex_id": iid, "name": i["name"], "country": i["country"],
            "works_count": i.get("works_count"), "cited_by_count": i.get("cited_by_count"),
            "h_index": i.get("h_index"),
        }

    # 领域（5 个主题）
    for cn, meta in FIELD_MAP.items():
        field_map[meta["id"]] = {
            "openalex_id": meta["id"], "name": meta["en"], "cn_label": cn, "level": meta["level"],
        }

    # 论文 -> 主题归属（用于 belongs_to_field）
    pub_topic = {}  # pub_id -> set(topic cn_label)
    for topic, works in works_by_topic.items():
        for w in works:
            pub_topic.setdefault(w["id"], set()).add(topic)

    # ===== 遍历论文 =====
    for w in works_all:
        pid = short(w["id"])
        # 期刊/会议
        src = (w.get("primary_location") or {}).get("source") or {}
        vid = short(src.get("id")) if src.get("id") else None
        if vid:
            venue_map[vid] = {
                "openalex_id": vid, "name": src.get("display_name"),
                "type": src.get("type"),
            }

        pub_map[pid] = {
            "openalex_id": pid, "doi": w.get("doi"), "title": (w.get("display_name") or w.get("title") or "")[:300],
            "year": w.get("publication_year"), "cited_by_count": w.get("cited_by_count"),
            "venue_id": vid, "type": w.get("type"),
        }

        # 学者 + 机构（来自 authorships）
        for a in w.get("authorships", []):
            au = a.get("author") or {}
            sid = short(au.get("id"))
            if not sid:
                continue
            if sid not in scholar_map:
                scholar_map[sid] = {
                    "openalex_id": sid, "name": au.get("display_name"), "orcid": au.get("orcid"),
                }
            # 作者-机构 归属
            for ainst in a.get("institutions", []):
                iid = short(ainst.get("id"))
                if iid and iid not in inst_map:
                    inst_map[iid] = {
                        "openalex_id": iid, "name": ainst.get("display_name"),
                        "country": ainst.get("country_code"), "works_count": None,
                        "cited_by_count": None, "h_index": None,
                    }
                # 记 scholar -> institution 边（后面单独建表）

    # ===== 关系表 =====
    author_of = []          # scholar_id, pub_id, position
    affiliation = []        # scholar_id, inst_id
    published_in = []       # pub_id, venue_id
    belongs_to_field = []   # pub_id, field_id
    affiliation_seen = set()

    for w in works_all:
        pid = short(w["id"])
        for a in w.get("authorships", []):
            sid = short((a.get("author") or {}).get("id"))
            if not sid:
                continue
            author_of.append({"scholar_id": sid, "pub_id": pid, "position": a.get("author_position")})
            for ainst in a.get("institutions", []):
                iid = short(ainst.get("id"))
                if iid and (sid, iid) not in affiliation_seen:
                    affiliation_seen.add((sid, iid))
                    affiliation.append({"scholar_id": sid, "inst_id": iid})
        vid = pub_map[pid]["venue_id"]
        if vid:
            published_in.append({"pub_id": pid, "venue_id": vid})
        for topic in pub_topic.get(w["id"], set()):
            fid = FIELD_MAP[topic]["id"]
            belongs_to_field.append({"pub_id": pid, "field_id": fid})

    # ===== 写入 CSV =====
    def write_csv(name, rows, cols):
        p = os.path.join(PROC, f"{name}.csv")
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            for r in rows:
                wr.writerow({c: r.get(c) for c in cols})
        print(f"  CSV {name}.csv: {len(rows)} 行")

    write_csv("institutions", list(inst_map.values()), ["openalex_id","name","country","works_count","cited_by_count","h_index"])
    write_csv("scholars", list(scholar_map.values()), ["openalex_id","name","orcid"])
    write_csv("publications", list(pub_map.values()), ["openalex_id","doi","title","year","cited_by_count","venue_id","type"])
    write_csv("venues", list(venue_map.values()), ["openalex_id","name","type"])
    write_csv("fields", list(field_map.values()), ["openalex_id","name","cn_label","level"])
    write_csv("author_of", author_of, ["scholar_id","pub_id","position"])
    write_csv("affiliation", affiliation, ["scholar_id","inst_id"])
    write_csv("published_in", published_in, ["pub_id","venue_id"])
    write_csv("belongs_to_field", belongs_to_field, ["pub_id","field_id"])

    # ===== 写入 DuckDB =====
    db = duckdb.connect(os.path.join(PROC, "academic.duckdb"))
    tables = {
        "institutions": ("institutions.csv", ["openalex_id","name","country","works_count","cited_by_count","h_index"]),
        "scholars": ("scholars.csv", ["openalex_id","name","orcid"]),
        "publications": ("publications.csv", ["openalex_id","doi","title","year","cited_by_count","venue_id","type"]),
        "venues": ("venues.csv", ["openalex_id","name","type"]),
        "fields": ("fields.csv", ["openalex_id","name","cn_label","level"]),
        "author_of": ("author_of.csv", ["scholar_id","pub_id","position"]),
        "affiliation": ("affiliation.csv", ["scholar_id","inst_id"]),
        "published_in": ("published_in.csv", ["pub_id","venue_id"]),
        "belongs_to_field": ("belongs_to_field.csv", ["pub_id","field_id"]),
    }
    for tname, (fname, cols) in tables.items():
        db.execute(f"CREATE OR REPLACE TABLE {tname} AS SELECT * FROM read_csv_auto('{os.path.join(PROC, fname)}')")
    db.close()

    # 打印汇总
    print("\n===== 数据汇总 =====")
    print(f"机构: {len(inst_map)}")
    print(f"学者: {len(scholar_map)}")
    print(f"论文: {len(pub_map)}")
    print(f"期刊/会议: {len(venue_map)}")
    print(f"领域: {len(field_map)}")
    print(f"author_of 边: {len(author_of)}")
    print(f"affiliation 边: {len(affiliation)}")
    print(f"belongs_to_field 边: {len(belongs_to_field)}")

if __name__ == "__main__":
    main()
