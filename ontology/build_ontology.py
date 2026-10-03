# -*- coding: utf-8 -*-
"""
平台本体（Platform Ontology）—— 平台的语义契约
含三个域：学术域 + 企业域 + 平台治理域（数据源）
本体不是摆设：它是「本体性转化」的目标 schema，也是工具自动生成的依据
"""
from owlready2 import *

onto_path.append(".")
onto = get_ontology("http://ecnu.edu.cn/ontology/platform#")

with onto:
    # ===== 平台治理域 =====
    class DataSource(Thing): pass          # 已接入的数据源（来源溯源）
    class Entity(Thing): pass              # 所有语义实体的根

    # ===== 学术域 =====
    class Scholar(Entity): pass
    class Institution(Entity): pass
    class Publication(Entity): pass
    class Venue(Entity): pass
    class Field(Entity): pass
    class Funder(Entity): pass
    class Dataset(Entity): pass

    # ===== 企业域（证明本体可扩展到非学术数据）=====
    class Company(Entity): pass
    class Industry(Entity): pass

    # ===== 通用域（承接任意上传的数据，保证"上传即可用"）=====
    class GenericRecord(Entity): pass

    # ===== 对象属性（关系）=====
    class sourcedFrom(ObjectProperty):
        """每个实体来自哪个数据源（溯源）"""
        domain = [Entity]
        range = [DataSource]

    class authorOf(ObjectProperty):
        domain = [Scholar]; range = [Publication]
    class affiliatedWith(ObjectProperty):
        domain = [Scholar]; range = [Institution]
    class publishedIn(ObjectProperty):
        domain = [Publication]; range = [Venue]
    class cites(ObjectProperty, TransitiveProperty):
        domain = [Publication]; range = [Publication]
    class fundedBy(ObjectProperty):
        domain = [Publication]; range = [Funder]
    class coAuthorWith(ObjectProperty, SymmetricProperty):
        domain = [Scholar]; range = [Scholar]
    class belongsToField(ObjectProperty):
        domain = [Publication, Scholar]; range = [Field]
    class belongsToIndustry(ObjectProperty):
        domain = [Company]; range = [Industry]
    class sameAs(ObjectProperty):
        domain = [Entity]; range = [Entity]

    class authoredBy(ObjectProperty):
        inverse_property = authorOf
    class hasAuthor(ObjectProperty):
        inverse_property = authorOf
    class citedBy(ObjectProperty):
        inverse_property = cites

    # ===== 数据属性 =====
    class name(DataProperty, FunctionalProperty):
        domain = [Entity]; range = [str]
    class openalex_id(DataProperty, FunctionalProperty):
        domain = [Entity]; range = [str]
    class year(DataProperty, FunctionalProperty):
        domain = [Publication]; range = [int]
    class doi(DataProperty, FunctionalProperty):
        domain = [Publication]; range = [str]
    class cited_by_count(DataProperty, FunctionalProperty):
        domain = [Publication]; range = [int]
    class country(DataProperty, FunctionalProperty):
        domain = [Institution]; range = [str]
    class level(DataProperty, FunctionalProperty):
        domain = [Field]; range = [int]
    class revenue(DataProperty, FunctionalProperty):
        """营收（亿元）"""
        domain = [Company]; range = [float]
    class employees(DataProperty, FunctionalProperty):
        """员工数"""
        domain = [Company]; range = [int]
    class region(DataProperty, FunctionalProperty):
        domain = [Company, Institution]; range = [str]
    class cnLabel(DataProperty):
        """中文标签（本体多语言标签，用于跨语言消歧）"""
        domain = [Entity]; range = [str]
    class description(DataProperty):
        domain = [Entity]; range = [str]
    # ===== 扩充数据属性（v2：机构/论文统计指标、数据集元数据）=====
    class worksCount(DataProperty, FunctionalProperty):
        domain = [Institution]; range = [int]
    class citedByCount(DataProperty, FunctionalProperty):
        domain = [Publication, Institution]; range = [int]
    class hIndex(DataProperty, FunctionalProperty):
        domain = [Institution]; range = [int]
    class publishedAt(DataProperty, FunctionalProperty):
        domain = [Publication]; range = [str]
    class size(DataProperty, FunctionalProperty):
        domain = [Dataset]; range = [str]
    class license(DataProperty, FunctionalProperty):
        domain = [Dataset]; range = [str]
    class url(DataProperty, FunctionalProperty):
        domain = [Dataset]; range = [str]

onto.save(file="ontology/platform.owl", format="rdfxml")
print("平台本体已保存: ontology/platform.owl")
print("类:", [c.name for c in onto.classes() if not c.name.startswith('owl')])
print("对象属性:", [p.name for p in onto.object_properties()])
