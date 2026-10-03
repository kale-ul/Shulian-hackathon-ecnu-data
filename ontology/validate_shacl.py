# -*- coding: utf-8 -*-
"""
SHACL 本体约束校验：验证数据是否满足本体定义的约束
证明「本体能做一致性校验」这一考点
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rdflib import Graph, Namespace, Literal, RDF
from pyshacl import validate

PROC = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
ONTO = Namespace("http://ecnu.edu.cn/ontology/academic#")
RES = Namespace("http://ecnu.edu.cn/resource/")

# 加载数据图
data_g = Graph()
data_g.parse(os.path.join(PROC, "academic_graph.ttl"), format="turtle")
print(f"数据图三元组数: {len(data_g)}")

# 定义 SHACL 约束
SH = Namespace("http://www.w3.org/ns/shacl#")
shapes = Graph()
shapes.bind("sh", SH)
shapes.bind("onto", ONTO)

def add_shape(shape_uri, target_class, prop, constraint, min_count=0):
    shapes.add((shape_uri, RDF.type, SH.NodeShape))
    shapes.add((shape_uri, SH.targetClass, target_class))
    prop_shape = RES[f"{shape_uri.split('#')[-1]}_{prop.split('#')[-1]}"]
    shapes.add((shape_uri, SH.property, prop_shape))
    shapes.add((prop_shape, SH.path, prop))
    shapes.add((prop_shape, constraint, Literal(min_count)))

# 约束 1：每篇论文必须有标题
add_shape(RES["PubHasTitle"], ONTO.Publication, ONTO.name, SH.minCount, 1)
# 约束 2：每篇论文必须有发表年份
add_shape(RES["PubHasYear"], ONTO.Publication, ONTO.year, SH.minCount, 1)
# 约束 3：每个学者必须至少有一篇论文（authorOf）
add_shape(RES["ScholarHasWork"], ONTO.Scholar, ONTO.authorOf, SH.minCount, 1)

conforms, report_g, report_text = validate(
    data_g, shacl_graph=shapes,
    data_graph_format="turtle", shacl_graph_format="turtle",
    inference="none", abort_on_first=False,
)
print(f"\nSHACL 校验结果: {'✅ 符合' if conforms else '❌ 不符合'}")
print(f"违规数: {len(list(report_g.objects(None, SH.result)))}")

# 打印违规详情（取前 5 条）
violations = []
for r in report_g.subjects(RDF.type, SH.ValidationResult):
    focus = report_g.value(r, SH.focusNode)
    path = report_g.value(r, SH.resultPath)
    sev = report_g.value(r, SH.resultSeverity)
    msg = report_g.value(r, SH.resultMessage)
    violations.append((str(focus), str(path).split('#')[-1] if path else None, str(msg)))
for v in violations[:5]:
    print(f"  违规: {v[0]} 缺少 {v[1]} — {v[2]}")
