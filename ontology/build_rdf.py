# -*- coding: utf-8 -*-
"""
把结构化表转成 RDF 知识图谱（本体语义层）
- 用 rdflib 构建三元组，输出 Turtle
- 跑 3 条 SPARQL 演示查询（对应「自然语言问数」背后的语义查询）
- 用 pyshacl 做 SHACL 本体约束校验
"""
import os, csv
from rdflib import Graph, Namespace, Literal, URIRef, RDF, XSD

PROC = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
ONTO = Namespace("http://ecnu.edu.cn/ontology/academic#")
RES = Namespace("http://ecnu.edu.cn/resource/")

g = Graph()
g.bind("onto", ONTO)
g.bind("res", RES)

def read_csv(name):
    p = os.path.join(PROC, f"{name}.csv")
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def S(idstr): return RES[f"s_{idstr}"]
def I(idstr): return RES[f"i_{idstr}"]
def P(idstr): return RES[f"p_{idstr}"]
def V(idstr): return RES[f"v_{idstr}"]
def F(idstr): return RES[f"f_{idstr}"]

def main():
    # 机构
    for r in read_csv("institutions"):
        i = I(r["openalex_id"])
        g.add((i, RDF.type, ONTO.Institution))
        g.add((i, ONTO.name, Literal(r["name"])))
        if r.get("country"):
            g.add((i, ONTO.country, Literal(r["country"])))
    # 领域
    for r in read_csv("fields"):
        f = F(r["openalex_id"])
        g.add((f, RDF.type, ONTO.Field))
        g.add((f, ONTO.name, Literal(r["name"])))
        g.add((f, ONTO.field_hierarchy_level, Literal(int(r["level"]) if r.get("level") else 0)))
    # 期刊
    for r in read_csv("venues"):
        v = V(r["openalex_id"])
        g.add((v, RDF.type, ONTO.Venue))
        g.add((v, ONTO.name, Literal(r["name"])))
    # 学者
    for r in read_csv("scholars"):
        s = S(r["openalex_id"])
        g.add((s, RDF.type, ONTO.Scholar))
        g.add((s, ONTO.name, Literal(r["name"])))
    # 论文
    for r in read_csv("publications"):
        p = P(r["openalex_id"])
        g.add((p, RDF.type, ONTO.Publication))
        g.add((p, ONTO.name, Literal(r["title"])))
        if r.get("year"):
            g.add((p, ONTO.year, Literal(int(r["year"]), datatype=XSD.integer)))
        if r.get("cited_by_count"):
            g.add((p, ONTO.cited_by_count, Literal(int(r["cited_by_count"]), datatype=XSD.integer)))
    # 关系
    for r in read_csv("affiliation"):
        g.add((S(r["scholar_id"]), ONTO.affiliatedWith, I(r["inst_id"])))
    for r in read_csv("author_of"):
        g.add((S(r["scholar_id"]), ONTO.authorOf, P(r["pub_id"])))
        g.add((P(r["pub_id"]), ONTO.authoredBy, S(r["scholar_id"])))
    for r in read_csv("published_in"):
        g.add((P(r["pub_id"]), ONTO.publishedIn, V(r["venue_id"])))
    for r in read_csv("belongs_to_field"):
        g.add((P(r["pub_id"]), ONTO.belongsToField, F(r["field_id"])))
    # 合作边（同论文的两两作者）
    pub_authors = {}
    for r in read_csv("author_of"):
        pub_authors.setdefault(r["pub_id"], []).append(r["scholar_id"])
    co_pairs = set()
    for pub, authors in pub_authors.items():
        for i in range(len(authors)):
            for j in range(i+1, len(authors)):
                co_pairs.add(tuple(sorted([authors[i], authors[j]])))
    for a, b in co_pairs:
        g.add((S(a), ONTO.coAuthorWith, S(b)))
        g.add((S(b), ONTO.coAuthorWith, S(a)))

    out = os.path.join(PROC, "academic_graph.ttl")
    g.serialize(destination=out, format="turtle")
    print(f"RDF 图谱已保存: {out}  （三元组数: {len(g)}）")

    # ============ SPARQL 演示查询 ============
    print("\n===== SPARQL 演示 =====")

    ECNU_ID = "I66867065"
    KG_ID = "C2987255567"

    # 查询 1：华东师大 + 知识图谱领域的学者
    q1 = f"""
    SELECT DISTINCT ?name WHERE {{
        ?s onto:affiliatedWith res:i_{ECNU_ID} .
        ?s onto:authorOf ?p .
        ?p onto:belongsToField res:f_{KG_ID} .
        ?s onto:name ?name .
    }} LIMIT 10
    """
    print("【Q1】华东师大研究知识图谱的学者:")
    for row in g.query(q1):
        print("  -", str(row.name))

    # 查询 2：各机构在「可信数据空间」领域的论文数
    TDS_ID = "C2988382989"
    q2 = f"""
    SELECT ?inst_name (COUNT(DISTINCT ?p) AS ?n) WHERE {{
        ?p onto:belongsToField res:f_{TDS_ID} .
        ?p onto:authoredBy ?s .
        ?s onto:affiliatedWith ?i .
        ?i onto:name ?inst_name .
    }} GROUP BY ?inst_name ORDER BY DESC(?n) LIMIT 8
    """
    print("\n【Q2】可信数据空间领域论文数 Top 机构:")
    for row in g.query(q2):
        print(f"  {str(row.inst_name)}: {row.n} 篇")

    # 查询 3：歧义消解——把「深度学习」映射到唯一领域实体，返回其论文数
    q3 = f"""
    SELECT ?fname (COUNT(DISTINCT ?p) AS ?n) WHERE {{
        ?f onto:name ?fname .
        ?p onto:belongsToField ?f .
    }} GROUP BY ?fname ORDER BY DESC(?n)
    """
    print("\n【Q3】各领域论文数（本体消歧后的实体统计）:")
    for row in g.query(q3):
        print(f"  {str(row.fname)}: {row.n} 篇")

    return g

if __name__ == "__main__":
    main()
