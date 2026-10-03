# -*- coding: utf-8 -*-
"""
智能体闭环：让真 LLM 自己选工具、调平台数据、出答案
完整链路：自然语言 → LLM 选工具(带参数) → 平台工具执行 → 数据 → LLM 生成答案
全程记录 trace（界面右侧实时展示）
"""
import json, re, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiplatform.llm import call_model
from aiplatform.tools import PlatformTools

TOOL_SPECS = [
    {"name": "list_ontology", "desc": "列出平台本体覆盖的类及实例数",
     "params": {}},
    {"name": "list_sources", "desc": "列出已接入的数据源",
     "params": {}},
    {"name": "explore_class", "desc": "探索某类实体（实例数+样例）",
     "params": {"class_name": "类名，如 Scholar/Company/Publication/Institution/Industry/Field/Venue"}},
    {"name": "find_entity", "desc": "按名称搜索某类实体",
     "params": {"class_name": "类名", "keyword": "关键词"}},
    {"name": "entity_detail", "desc": "查看实体的属性与关系",
     "params": {"entity_id": "实体ID，如 c_C001"}},
    {"name": "query_relation", "desc": "查询某类关系，如 学者-所属机构",
     "params": {"subject_class": "主体类", "relation": "关系名", "object_class": "客体类"}},
    {"name": "sparql", "desc": "执行 SPARQL 查询（高级）",
     "params": {"query": "SPARQL 语句"}},
    {"name": "semantic_ask", "desc": "自然语言问数：学术数据（学者/论文/领域）+ 企业数据（公司/行业）",
     "params": {"question": "完整的自然语言问题"}},
]

SYSTEM = """你是接入「面向 AI 的科研数据平台」的智能体。
你需要把用户的问题转成一次平台工具调用。

可用工具：
%s

规则：
1. 优先使用 semantic_ask（它能覆盖学术+企业数据的自然语言问数），把用户原问题放进 question 参数。
2. 只有当问题明显是"平台自身信息"（有哪些数据源、本体有哪些类）时，才用 list_sources / list_ontology。
3. 只输出一个 JSON，不要解释。格式：{"tool": "工具名", "params": {...}, "reason": "为什么选这个工具"}
""" % json.dumps(TOOL_SPECS, ensure_ascii=False)


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            return json.loads(m.group(0).replace("'", '"'))
        except Exception:
            return None


class DataAgent:
    """接入平台数据工具的真 LLM 智能体"""
    def __init__(self, graph, catalog, provider_name=None, model=None):
        self.pt = PlatformTools(graph)
        self.catalog = catalog
        from aiplatform.llm import list_models
        ms = list_models()
        self.provider_name = provider_name or (ms[0]["provider"] if ms else None)
        self.model = model or (ms[0]["model"] if ms else None)

    def set_model(self, provider_name, model):
        self.provider_name = provider_name
        self.model = model

    def _run_tool(self, tool, params):
        pt = self.pt
        if tool == "list_sources":
            return pt.list_sources(self.catalog)
        if tool == "list_ontology":
            return pt.list_ontology()
        if not hasattr(pt, tool):
            return {"error": f"未知工具 {tool}"}
        try:
            return getattr(pt, tool)(**params)
        except Exception as e:
            return {"error": str(e)}

    def ask(self, question, use_llm=True):
        """返回 {question, trace[], result, answer, model_used}"""
        trace = []
        t0 = time.time()

        # 1) LLM 选工具
        parsed = None
        if use_llm:
            try:
                resp = call_model(self.provider_name, self.model,
                                  [{"role": "system", "content": SYSTEM},
                                   {"role": "user", "content": question}],
                                  max_tokens=400)
                trace.append({"step": "① LLM 选择工具", "model": self.model,
                              "backend": resp.get("backend"), "raw": resp.get("content", "")[:200]})
                parsed = _extract_json(resp.get("content", ""))
            except Exception as e:
                trace.append({"step": "① LLM 选择工具", "error": str(e)})

        # 2) 兜底：语义路由
        if not parsed or parsed.get("tool") not in [t["name"] for t in TOOL_SPECS]:
            parsed = {"tool": "semantic_ask", "params": {"question": question},
                      "reason": "LLM 解析失败，回退到平台语义路由"}
            trace.append({"step": "① 兜底路由", "tool": parsed["tool"]})

        tool = parsed["tool"]
        params = dict(parsed.get("params", {}))
        # 修正：semantic_ask 缺少 question 时补上原问题
        if tool == "semantic_ask" and "question" not in params:
            params["question"] = question
        trace.append({"step": "② 选定工具与参数", "tool": tool, "params": params,
                      "reason": parsed.get("reason", "")})

        # 3) 执行工具
        result = self._run_tool(tool, params)
        ok = "error" not in result
        trace.append({"step": "③ 平台执行工具", "tool": tool, "ok": ok,
                      "preview": json.dumps(result, ensure_ascii=False)[:200]})

        # 4) LLM 生成自然语言答案
        answer = ""
        if use_llm and ok:
            try:
                am = call_model(self.provider_name, self.model, [
                    {"role": "system", "content": "你是数据平台助手。根据查询结果用简洁中文回答用户问题，可列点，不要编造结果之外的数据。"},
                    {"role": "user", "content": f"用户问题：{question}\n\n平台返回数据：\n{json.dumps(result, ensure_ascii=False)}"},
                ], max_tokens=600)
                answer = am.get("content", "")
                trace.append({"step": "④ LLM 生成答案", "model": self.model, "len": len(answer)})
            except Exception as e:
                trace.append({"step": "④ LLM 生成答案", "error": str(e)})

        trace.append({"step": "完成", "elapsed_ms": int((time.time() - t0) * 1000)})
        return {"question": question, "trace": trace, "result": result,
                "answer": answer, "model_used": f"{self.provider_name} / {self.model}"}


if __name__ == "__main__":
    from aiplatform.build_platform import build
    onto, cat, graph = build()
    agent = DataAgent(graph.g, cat)
    for q in ["华东师大哪些老师研究知识图谱？", "平台接入了哪些数据源？"]:
        out = agent.ask(q)
        print("\n" + "=" * 60)
        print("Q:", q, "| model:", out["model_used"])
        for t in out["trace"]:
            print("  ", json.dumps(t, ensure_ascii=False)[:180])
        print("答案:", out["answer"][:300])
