# -*- coding: utf-8 -*-
"""
平台对外端口 —— OpenAI 兼容 API 服务

任何 AI 客户端（ChatGPT / DeepSeek / 豆包 / Cursor / Dify / LangChain / 自研 Agent…）
只要把 base_url 指到本服务，就能调用平台的数据能力。

端点：
  GET  /v1/models                 列出平台暴露的「模型」（= 数据能力）
  POST /v1/chat/completions       OpenAI 兼容对话接口（核心）
  GET  /v1/tools                  列出平台的本体驱动工具
  POST /v1/tools/{tool}           直接调用某个工具（给 Agent 用）
  GET  /health                    健康检查

启动：
  python -m aiplatform.api_server            # 默认 0.0.0.0:8610
"""
import os, sys, json, time, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from aiplatform.build_platform import build
from aiplatform.semantic import GenericSemanticQuery
from aiplatform.tools import PlatformTools

app = FastAPI(title="面向 AI 的大数据平台 · OpenAI 兼容端点",
              description="把本体化数据能力暴露为标准 OpenAI 接口，任何 AI 客户端可接入",
              version="1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

# ---------- 平台初始化（进程内单例）----------
_onto = _cat = _graph = _q = _tools = None


def get_platform():
    global _onto, _cat, _graph, _q, _tools
    if _graph is None:
        _onto, _cat, _graph = build()
        _q = GenericSemanticQuery(_graph.g)
        _tools = PlatformTools(_graph, _cat)
    return _onto, _cat, _graph, _q, _tools


# ---------- 平台工具清单（本体驱动，供任意 Agent 调用）----------
TOOL_SPECS = [
    {"name": "list_ontology", "description": "列出平台本体的类、关系、属性",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "list_sources", "description": "列出平台已接入的数据源",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "explore_class", "description": "浏览某个本体类的实例",
     "parameters": {"type": "object", "properties": {
         "class_name": {"type": "string", "description": "本体类，如 Scholar/Publication/Company"},
         "limit": {"type": "integer", "default": 5}}, "required": ["class_name"]}},
    {"name": "find_entity", "description": "按关键词在某个类里查找实体",
     "parameters": {"type": "object", "properties": {
         "class_name": {"type": "string"}, "keyword": {"type": "string"},
         "limit": {"type": "integer", "default": 10}}, "required": ["class_name", "keyword"]}},
    {"name": "entity_detail", "description": "查看某实体的完整信息（属性 + 关系）",
     "parameters": {"type": "object", "properties": {
         "entity_id": {"type": "string"}}, "required": ["entity_id"]}},
    {"name": "query_relation", "description": "按关系查询：某类的实体通过某关系指向另一类",
     "parameters": {"type": "object", "properties": {
         "subject_class": {"type": "string"}, "relation": {"type": "string"},
         "object_class": {"type": "string"}, "limit": {"type": "integer", "default": 20}},
         "required": ["subject_class", "relation", "object_class"]}},
    {"name": "sparql", "description": "对统一知识图谱执行 SPARQL 查询",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string"}}, "required": ["query"]}},
    {"name": "semantic_ask", "description": "自然语言问数（本体语义解析）",
     "parameters": {"type": "object", "properties": {
         "question": {"type": "string"}}, "required": ["question"]}},
]


# ---------- 请求模型 ----------
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: Optional[str] = "platform-semantic"
    messages: List[Message]
    temperature: Optional[float] = 0
    max_tokens: Optional[int] = 600
    stream: Optional[bool] = False


class ToolCallRequest(BaseModel):
    arguments: Dict[str, Any] = {}


# ---------- 对外暴露的「模型」= 平台的数据能力 ----------
PLATFORM_MODELS = [
    {"id": "platform-semantic", "object": "model", "owned_by": "ai-data-platform",
     "description": "本体驱动的语义查询：自然语言 → 本体 → 数据"},
    {"id": "platform-tools", "object": "model", "owned_by": "ai-data-platform",
     "description": "工具调用模式：返回平台可用的工具清单"},
    {"id": "platform-graph", "object": "model", "owned_by": "ai-data-platform",
     "description": "知识图谱直查：实体/关系/统计"},
]


@app.get("/health")
def health():
    onto, cat, graph, q, tools = get_platform()
    st = graph.stats()
    return {"status": "ok", "sources": len(cat.list()), "triples": st["triples"],
            "entities": st["entities"], "classes": st["classes"]}


@app.get("/v1/models")
def models():
    """OpenAI 兼容：列出模型（这里 = 平台暴露的数据能力）"""
    return {"object": "list", "data": PLATFORM_MODELS}


@app.get("/v1/tools")
def list_tools():
    """列出平台的本体驱动工具（供任意 Agent 使用）"""
    return {"tools": TOOL_SPECS}


@app.post("/v1/tools/{tool_name}")
def call_tool(tool_name: str, req: ToolCallRequest):
    """直接调用平台工具（Agent 用）"""
    onto, cat, graph, q, tools = get_platform()
    args = dict(req.arguments or {})
    try:
        if tool_name == "list_ontology":
            result = tools.list_ontology()
        elif tool_name == "list_sources":
            result = tools.list_sources(cat)
        elif tool_name == "explore_class":
            result = tools.explore_class(args.get("class_name"), args.get("limit", 5))
        elif tool_name == "find_entity":
            result = tools.find_entity(args.get("class_name"), args.get("keyword"),
                                       args.get("limit", 10))
        elif tool_name == "entity_detail":
            result = tools.entity_detail(args.get("entity_id"))
        elif tool_name == "query_relation":
            result = tools.query_relation(args.get("subject_class"), args.get("relation"),
                                          args.get("object_class"), args.get("limit", 20))
        elif tool_name == "sparql":
            result = tools.sparql(args.get("query"))
        elif tool_name == "semantic_ask":
            result = tools.semantic_ask(args.get("question"))
        else:
            raise HTTPException(status_code=404, detail=f"未知工具 {tool_name}")
        return {"tool": tool_name, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    """
    OpenAI 兼容对话接口。
    平台把最后一条 user 消息当作自然语言问句，走本体语义查询，
    再把结构化结果作为上下文返回（外部 AI 可据此生成自然语言答案）。
    """
    onto, cat, graph, q, tools = get_platform()

    user_msgs = [m.content for m in req.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="缺少 user 消息")
    question = user_msgs[-1]

    t0 = time.time()
    try:
        result = q.ask(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")

    # 组织成 OpenAI 兼容的回答：先自然语言摘要，再附结构化数据
    summary = _summarize(question, result)
    content = summary + "\n\n```json\n" + json.dumps(result, ensure_ascii=False, indent=1)[:3000] + "\n```"

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or "platform-semantic",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": len(question), "completion_tokens": len(content),
                  "total_tokens": len(question) + len(content)},
        "platform": {"intent": result.get("intent"), "elapsed_ms": int((time.time() - t0) * 1000)},
    }


def _summarize(question, r):
    """把结构化查询结果转成简短中文摘要（外部 AI 可再加工）"""
    it = r.get("intent")
    if it == "relation_rank" and r.get("data"):
        top = r["data"][:5]
        return f"【平台查询结果】{r.get('subject')} 排名前 5：" + \
               "、".join(f"{x['name']}({x['count']})" for x in top)
    if it == "numeric_rank" and r.get("data"):
        top = r["data"][:5]
        return "【平台查询结果】数值排名前 5：" + \
               "、".join(f"{x['name']}({x['value']})" for x in top)
    if it == "industry_companies":
        return f"【平台查询结果】{r.get('industry')} 行业共 {r.get('count')} 家公司：" + \
               "、".join(x["name"] for x in r.get("companies", [])[:15])
    if it == "field_entities":
        return f"【平台查询结果】{r.get('field')} 领域共 {r.get('count')} 项：" + \
               "；".join(str(x)[:50] for x in r.get("entities", [])[:8])
    if it == "scholars_filtered":
        return f"【平台查询结果】共 {r.get('count')} 位相关学者，前 15 位：" + \
               "、".join(r.get("scholars", [])[:15])
    if it == "institution_members":
        return f"【平台查询结果】{r.get('institution')} 共 {r.get('count')} 位成员。"
    if it == "list_class":
        return f"【平台查询结果】{r.get('class')} 共 {r.get('count')} 个实例。"
    if it == "search_entities":
        return f"【平台查询结果】关键词「{r.get('keyword')}」命中 {r.get('count')} 个实体。"
    if it == "overview":
        return "【平台查询结果】平台本体实例分布：" + \
               "、".join(f"{k}:{v}" for k, v in (r.get("classes") or {}).items())
    if it == "entity_detail":
        return f"【平台查询结果】{r.get('entity')}（{r.get('class')}）详情已返回。"
    return "【平台查询结果】已返回结构化数据，详见 JSON。"


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PLATFORM_API_PORT", "8610"))
    print(f"平台对外端点启动：http://0.0.0.0:{port}")
    print(f"  OpenAI 兼容： POST http://localhost:{port}/v1/chat/completions")
    print(f"  模型列表   ： GET  http://localhost:{port}/v1/models")
    print(f"  工具列表   ： GET  http://localhost:{port}/v1/tools")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
