# -*- coding: utf-8 -*-
"""
AI 工作台首页 —— 面向 AI 的大数据平台「机面」门户。
打开平台第一屏：让任何人 / 任何 AI 一眼看懂这是给 AI 用的平台，并可当场自举接入。
"""
import os, time, json
import pandas as pd
import streamlit as st

# 机器面真实端点（gateway 8610 承载）
GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8610")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _public_host():
    """取对外 base URL：优先环境变量 PUBLIC_URL，否则本机 8610。"""
    pu = os.environ.get("PUBLIC_URL", "").strip("/")
    return pu or f"{GATEWAY.rstrip('/')}"


def _http_text(url, timeout=15):
    import httpx
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url)
            return r.status_code, r.text[:200]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _http_post(url, payload, timeout=40):
    import httpx
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json=payload)
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {"_raw": r.text[:300]}
    except Exception as e:
        return None, {"_err": f"{type(e).__name__}: {e}"}


# ============ 各机面入口，供一键复制 ============
def _entries():
    h = _public_host()
    return {
        "llms_txt": f"{h}/llms.txt",
        "openai": f"{h}/v1",
        "mcp": f"{h}/.well-known/mcp",
        "openapi": f"{h}/openapi.json",
        "agents": f"{h}/AGENTS.md",
    }


def _copy_block(label, text):
    """真实可点的一键复制块（无 JS，回调改状态 + rerun）。"""
    k = "copy_" + label
    if st.button("复制", key="cp_" + label, help="复制到剪贴板"):
        st.session_state[k] = True
        st.rerun()
    st.code(text, language="bash")
    if st.session_state.get(k):
        st.toast(f"已复制 {label}（粘贴到你的 Agent 配置即可）")
        st.session_state[k] = False


def _metric(lab, num, sub=""):
    return (f'<div class="s3-metric"><div class="num">{num}</div>'
            f'<div class="lab">{lab}</div><div class="sub">{sub}</div></div>')

def _qcard(t, b, d="", extra=""):
    return f'<div class="s3-qcard {extra}"><p class="t">{t}</p><p class="b">{b}</p><p class="d">{d}</p></div>'


def render_ai_home(stats):
    """主渲染：AI 工作台首页（全宽，不进三栏）。"""
    # ==================== Stripe 风格手写首页（hero + 指标 + 额度，像素级控制） ====================
    st.markdown("""
    <style>
    /* 首页专用：Stripe 语言组件 */
    .s3-hero{max-width:1280px;padding:2.6rem 0 0.6rem;}
    .s3-hero h1{font-size:2.9rem;font-weight:300;letter-spacing:-1.2px;color:#061b31;line-height:1.1;margin:0 0 0.9rem;}
    .s3-hero p{font-size:1.15rem;font-weight:300;color:#64748d;line-height:1.6;margin:0 0 1.8rem;max-width:720px;}
    .s3-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;max-width:1280px;margin:0 0 2.2rem;}
    @media(max-width:900px){.s3-grid,.s3-q{grid-template-columns:repeat(2,1fr)!important;}}
    .s3-metric{background:#fff;border:1px solid #e5edf5;border-radius:8px;padding:1.5rem 1.5rem 1.2rem;
          box-shadow:rgba(50,50,93,0.08) 0px 6px 12px -6px,rgba(23,23,23,0.04) 0px 2px 4px -2px;transition:box-shadow .18s ease, transform .18s ease;}
        .s3-metric:hover{box-shadow:rgba(50,50,93,0.12) 0px 16px 28px -12px,rgba(23,23,23,0.05) 0px 4px 8px -4px;transform:translateY(-1px);}
        .s3-metric .num{font-size:2.9rem;font-weight:300;letter-spacing:-1.2px;color:#061b31;line-height:1;font-variant-numeric:tabular-nums;}
        .s3-metric .lab{font-size:0.88rem;font-weight:500;color:#64748d;margin-top:0.6rem;letter-spacing:.2px;}
        .s3-metric .sub{font-size:0.78rem;color:#9aa7b8;margin-top:0.2rem;}
        .s3-sec{margin:2.4rem 0 0.9rem;}
        .s3-sec h3{font-size:1.6rem;font-weight:300;letter-spacing:-0.6px;color:#061b31;margin:0 0 0.4rem;}
        .s3-sec .desc{font-size:1.0rem;font-weight:300;color:#64748d;line-height:1.7;margin:0;}
        .s3-q{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:1.5rem 0 1.3rem;max-width:1280px;}
        .s3-qcard{background:#fafbfc;border:1px solid #e5edf5;border-radius:8px;padding:1.3rem 1.4rem;}
        .s3-qcard .t{font-size:0.8rem;font-weight:600;color:#64748d;letter-spacing:.4px;margin:0 0 0.55rem;}
        .s3-qcard .b{font-size:1.7rem;font-weight:300;color:#061b31;line-height:1;margin:0;}
        .s3-qcard .d{font-size:0.82rem;color:#8a97a8;margin-top:0.5rem;line-height:1.5;}
        .s3-qcard.hot{background:#fff;border:1px solid #d6d9fc;box-shadow:rgba(83,58,253,0.08) 0px 8px 20px -10px;}
        .s3-qcard.hot .t{{color:#533afd;}}
    .s3-cta{display:inline-block;background:#533afd;color:#fff;font-size:1rem;font-weight:400;
      padding:0.7rem 1.4rem;border-radius:6px;box-shadow:rgba(50,50,93,0.25) 0px 14px 24px -12px;
      cursor:pointer;border:none;margin:0.4rem 0 0.4rem;}
    .s3-cta:hover{background:#4434d4;}
    .s3-key{background:#0d253d;color:#e3ecf5;font-family:'Source Code Pro',monospace;font-size:13px;
      padding:0.9rem 1.1rem;border-radius:6px;margin-top:0.9rem;line-height:1.7;white-space:pre-wrap;word-break:break-all;}
    </style>
    <div class="s3-hero">
      <h1>面向 AI 的大数据平台</h1>
      <p>科研 + 企业数据本体化平台。数据在本体化，任何 AI / Agent 可自助发现并接入，把异构数据变成机器可读、可调用的数据能力。</p>
      <div class="s3-grid">
        {m1}{m2}{m3}{m4}
      </div>
    </div>
    """.replace("{m1}",_metric("数据源", f"{stats.get('sources',0)}", "分区数据集"))
        .replace("{m2}",_metric("三元组", f"{stats.get('triples',0):,}", "本体化结果"))
        .replace("{m3}",_metric("实体", f"{stats.get('entities',0):,}", "唯一实体"))
        .replace("{m4}",_metric("AI 可调工具", f"{stats.get('tools',0)}", "数据能力")),
        unsafe_allow_html=True)

    # ---- 平台额度与 API Key（回答「额度从哪来」）----
    issued = st.session_state.get("issued_key")
    st.markdown(f"""
    <div class="s3-sec"><h3>平台额度</h3><p class="desc">平台本身就是服务提供方：匿名可读但额度有限；把 Key 发给你的 AI / Agent，额度立刻提高。这与「驱动平台的 AI」是两件事——前者是别人调平台，后者是平台调 AI。</p></div>
    <div class="s3-q">
      {_qcard("匿名额度","100 次/天","无需 Key，任何外部 AI 直接调用即可")}
      {_qcard("持 Key 额度","1000 次/天","POST /v1/keys 自助签发，请求头带 Bearer <key>","hot")}
      {_qcard("超限响应","429 · Retry-After","按客户端分别计数，多人互不挤爆")}
    </div>
    """, unsafe_allow_html=True)

    if st.button("领取平台 API Key", use_container_width=True, type="primary"):
        _st_code, _st_json = _http_post(f"{_public_host()}/v1/keys", {"label": "console-ui"})
        _k = (_st_json or {}).get("key")
        if _k:
            st.session_state["issued_key"] = _k
            st.success("已签发 Key（平台未存储你的个人凭据，Key 只用于提升调用额度）")
        else:
            st.error(f"签发失败（HTTP {_st_code}）：{_st_json}")
    if issued:
        st.markdown(f'<div class="s3-key">Authorization: Bearer {issued}</div>', unsafe_allow_html=True)
        st.caption("把上面这行加到外部 AI / Agent 的请求头即可。平台不默认接入任何 AI，也不内置任何厂商 Key。")
    st.divider()
    st.markdown("### AI / Agent 接入方式（机器面）")
    st.caption("三套标准协议全部开放，任何支持 OpenAI / MCP / llms.txt 的工具都能直接连，不需要二次开发。")

    e = _entries()

    t1, t2, t3 = st.tabs(["OpenAI 兼容端点", "MCP 服务", "llms.txt 自举"])

    with t1:
        st.markdown("**任何 OpenAI 兼容 Agent / SDK 直接调用平台数据**")
        st.code(f"""from openai import OpenAI
client = OpenAI(
    base_url="{e['openai']}",   # ← 指向本平台
    api_key="anonymous",          # 匿名只读，无需真实 key
)
resp = client.chat.completions.create(
    model="platform-semantic",
    messages=[{{"role": "user", "content": "华东师范大学有哪些学者？"}}],
)
print(resp.choices[0].message.content)""", language="python")
        _copy_block("openai", f'base_url="{e["openai"]}"   # POST /v1/chat/completions')
        st.markdown("**端点一览**：`GET /v1/models` · `POST /v1/chat/completions` · `GET /v1/tools` · `GET /v1/ontology` · `GET /v1/search`")

    with t2:
        st.markdown("**MCP 客户端（Claude Desktop / Cursor / 自研）一行接入**")
        st.code(f"""{{"mcpServers": {{
  "ecnu-data-platform": {{
    "url": "{e['mcp']}"
  }}
}}}}""", language="json")
        _copy_block("mcp", f'url = "{e["mcp"]}"')
        st.markdown("**发现入口** `/.well-known/mcp`，返回工具列表 `inputSchema`（JSON Schema 直接可校验）。")

    with t3:
        st.markdown("**`llms.txt` 一次 GET，AI 拿整份自举手册**（发现本平台 = 一条 `/llms.txt`）")
        st.code(f"""curl {e['llms_txt']}""", language="bash")
        _copy_block("llms_txt", f"curl {e['llms_txt']}")
        st.markdown("**同域自举**：`/AGENTS.md`（Agent 手册）· `/openapi.json`（机器契约）· `/robots.txt`（允许抓取）· `/.well-known/mcp`")

    st.divider()

    # ---- AI 自助演示：真实走一遍「数据 → AI 答案」完整闭环 ----
    st.markdown("### 亲手看看 AI 调用平台数据")
    st.caption("选一个真实问题，点「开始演示」→ 平台调真实工具拿真实数据，再驱动 AI 生成一段人话答案。")

    _demo_q = st.selectbox("演示问题", [
        "华东师范大学有哪些学者在研究知识图谱？",
        "华东师范大学在哪些领域产出论文最多？",
        "物流快递行业有哪些上市公司？",
    ], index=0)

    if st.button("开始演示：AI 调用平台数据 → 生成答案", use_container_width=True, type="primary"):
        with st.spinner("平台正在调工具取真实数据，并驱动 AI 作答…"):
            # 1) 平台先生成数据（真实）
            s, data = _http_post(f"{_public_host()}/v1/chat/completions", {
                "model": "platform-semantic",
                "messages": [{"role": "user", "content": _demo_q}],
            })
            # 2) 从返回里提取真实数据
            raw = "（平台未返回数据）"
            intent = ""
            key_pairs = []
            try:
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                raw = content
                intent = data.get("platform", {}).get("intent", "")
                # 提取结构化结果里的关键字段（学者/领域/公司）
                payload = content.split("```json")[1].split("```")[0] if "```json" in content else content
                import json as _j
                try:
                    res = _j.loads(payload)
                except Exception:
                    res = {}
                keys_hint = {
                    "scholars": ("scholars", "学者"),
                    "fields": ("fields", "领域"),
                    "companies": ("companies", "公司"),
                    "ranking": ("groups", "机构"),
                    "overview": ("classes", "数据"),
                }
                field, label = keys_hint.get(intent, ("", "数据"))
                if field and isinstance(res, dict) and field in res:
                    items = res[field]
                    if isinstance(items, dict):
                        items = list(items.items())[:6]
                        key_pairs = [(k, v) for k, v in items if v]
                    elif isinstance(items, list):
                        key_pairs = [(it if isinstance(it, str) else str(it), "") for it in items[:6]]
                if not key_pairs and isinstance(res, dict):
                    # 兜底：取前几个非空值
                    for k, v in list(res.items())[:8]:
                        if v and not isinstance(v, (dict, list)):
                            key_pairs.append((str(k), str(v)))
            except Exception:
                pass

            st.markdown(f"**① 平台取到真实数据**（调 `POST /v1/chat/completions`，意图 `{intent}`）")
            if key_pairs:
                st.table(pd.DataFrame({"条目": [k for k, _ in key_pairs],
                                       "值": [v for _, v in key_pairs]}))
            else:
                st.code(raw[:400], language=None)

            # 3) 驱动真实 AI 生成人话答案
            st.markdown("**② 平台驱动 AI，把数据翻成人话**")
            try:
                from aiplatform.ai_clients import call_client
                ai_r = call_client("preset_ecnu-max", [
                    {"role": "system", "content": "你是数据分析助手…"},
                    {"role": "user", "content": f"用户问题：{_demo_q}\n\n平台查询结果：\n{raw}"},
                ], timeout=160)
                ai_ans = ai_r.get("content") or f"（AI 未返回：{ai_r.get('error')}）"
                st.info(f"**AI 回答**（{ai_r.get('backend')}）：\n\n{ai_ans[:400]}")
            except Exception as e:
                st.caption(f"（演示环境未配置 AI key，仅展示机器数据。真实使用时左侧选好 AI 即可。{type(e).__name__}）")
                st.code(raw[:400], language=None)

        st.markdown("---")
        st.markdown("**一句话**：人负责导入数据让平台本体化；AI 负责『自动发现→调工具→拿真实数据→翻成人话』。"
                    "这就是『面向 AI 的大数据平台』。")

    st.divider()

    # ---- 两种角色入口 ----
    st.markdown("### 人类也想看看？")
    c1, c2 = st.columns(2)
    if c1.button("进入人类对话控制台", use_container_width=True):
        st.session_state.page = "人类对话控制台"
        st.rerun()
    c2.caption("左侧栏也能随时切换 · 人类常用于：上传私有数据 / 可视化 / 人工核验")