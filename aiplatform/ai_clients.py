# -*- coding: utf-8 -*-
"""
多 AI 接入层 v2 —— 平台是「对外产品」，不绑定任何一家 AI

设计原则：
1. 平台对外暴露 **标准 OpenAI 兼容端点**（见 aiplatform/api_server.py），
   任何 AI 客户端 / 智能体框架连上这个端口就能用平台的数据能力。
2. 平台内的「AI 客户端登记表」是**开放的**：任意 OpenAI 兼容服务
   （DeepSeek / Qwen / 豆包 / Kimi / 智谱 / OpenAI / 本地 Ollama / 自建 vLLM…）
   只要填 base_url + api_key + model 就能接入，不需要改代码。
3. 内置常见厂商预设（一键填），但预设只是方便，不是限制。
4. 登记信息存 ai_clients.json；key 也可以放在环境变量里（推荐）。

客户端实际存储：
  ai_clients.json  →  [{key, name, kind, model, base_url, api_key_env, api_key, note}]
"""
import hashlib
import os, json, subprocess, shutil, time
import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(BASE, "ai_clients.json")
CODEX_PATHS = [
    r"C:\Users\gybao\AppData\Local\OpenAI\Codex\bin\12219cbfbcbddde7\codex.exe",
]

# ============ 常见厂商预设（点一下就填好，也可手动改）============
PRESETS = [
    {"name": "华东师大开放平台 · ecnu-max", "model": "ecnu-max",
     "base_url": "https://chat.ecnu.edu.cn/open/api/v1", "api_key_env": "CHATECNU-API-KEY",
     "note": "ECNU 开放平台（后端 DeepSeek）"},
    {"name": "华东师大开放平台 · ecnu-plus", "model": "ecnu-plus",
     "base_url": "https://chat.ecnu.edu.cn/open/api/v1", "api_key_env": "CHATECNU-API-KEY",
     "note": "ECNU 开放平台（后端 Qwen）"},
    {"name": "DeepSeek 官方 · deepseek-chat", "model": "deepseek-chat",
     "base_url": "https://api.deepseek.com/v1", "api_key_env": "DEEPSEEK_API_KEY",
     "note": "DeepSeek 官方 API"},
    {"name": "通义千问 · qwen-plus", "model": "qwen-plus",
     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "api_key_env": "DASHSCOPE_API_KEY", "note": "阿里云 DashScope 兼容模式"},
    {"name": "豆包 · doubao-pro", "model": "doubao-pro-32k",
     "base_url": "https://ark.cn-beijing.volces.com/api/v3", "api_key_env": "ARK_API_KEY",
     "note": "火山方舟 Ark"},
    {"name": "Kimi · moonshot-v1-8k", "model": "moonshot-v1-8k",
     "base_url": "https://api.moonshot.cn/v1", "api_key_env": "MOONSHOT_API_KEY",
     "note": "月之暗面 Kimi"},
    {"name": "智谱 GLM · glm-4-flash", "model": "glm-4-flash",
     "base_url": "https://open.bigmodel.cn/api/paas/v4", "api_key_env": "ZHIPU_API_KEY",
     "note": "智谱 AI"},
    {"name": "硅基流动 · Qwen2.5", "model": "Qwen/Qwen2.5-72B-Instruct",
     "base_url": "https://api.siliconflow.cn/v1", "api_key_env": "SILICONFLOW_API_KEY",
     "note": "SiliconFlow 聚合"},
    {"name": "OpenAI · gpt-4o-mini", "model": "gpt-4o-mini",
     "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY",
     "note": "OpenAI 官方（需代理）"},
    {"name": "本地 Ollama · qwen2.5", "model": "qwen2.5",
     "base_url": "http://localhost:11434/v1", "api_key_env": "OLLAMA_API_KEY",
     "note": "本地部署，无需联网"},
    {"name": "自建 vLLM / 任意兼容服务", "model": "your-model",
     "base_url": "http://localhost:8000/v1", "api_key_env": "VLLM_API_KEY",
     "note": "任意 OpenAI 兼容端点，填 URL 即可"},
]


class AIClient:
    def __init__(self, key, name, kind, model, note="", base_url=None,
                 api_key=None, api_key_env=None, **kw):
        self.key, self.name, self.kind, self.model, self.note = key, name, kind, model, note
        self.base_url = base_url
        self.api_key_env = api_key_env
        self._api_key = api_key
        self.extra = kw

    @property
    def api_key(self):
        """优先环境变量（更安全），其次登记表里的明文"""
        if self.api_key_env:
            v = os.environ.get(self.api_key_env) or os.environ.get(self.api_key_env.replace("-", "_"))
            if v:
                return v
        return self._api_key

    def available(self):
        if self.kind == "http":
            return bool(self.api_key) and bool(self.base_url)
        return True


# ============ 登记表读写 ============
def _load_registry():
    if not os.path.exists(REGISTRY):
        return []
    try:
        with open(REGISTRY, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_registry(items):
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def register_client(name, base_url, model, api_key=None, api_key_env=None, note="", key=None):
    """登记一个任意 OpenAI 兼容 AI 服务（对外产品形态：填 URL + key 即可）"""
    items = _load_registry()
    digest = hashlib.sha256(f"{name}|{base_url}|{model}".encode("utf-8")).hexdigest()[:10]
    k = key or f"custom_{int(digest, 16) % 100000}"
    items = [i for i in items if i.get("key") != k]
    items.append({"key": k, "name": name, "kind": "http", "model": model,
                  "base_url": base_url.rstrip("/"), "api_key": api_key,
                  "api_key_env": api_key_env, "note": note or "自定义 OpenAI 兼容服务"})
    _save_registry(items)
    return k


def unregister_client(key):
    items = [i for i in _load_registry() if i.get("key") != key]
    _save_registry(items)


def _find_codex():
    for p in CODEX_PATHS:
        if os.path.exists(p):
            return p
    return shutil.which("codex")


def build_clients():
    """扫描环境 + 登记表 + 本地 Agent，构建可用 AI 客户端列表"""
    clients, seen = [], set()

    # ---- 1. 内置厂商预设：只要环境变量里有 key 就自动出现 ----
    for p in PRESETS:
        if os.environ.get(p["api_key_env"]) or os.environ.get(p["api_key_env"].replace("-", "_")):
            k = f"preset_{p['model']}"
            if k in seen:
                continue
            seen.add(k)
            clients.append(AIClient(k, p["name"], "http", p["model"], p["note"],
                                    base_url=p["base_url"], api_key_env=p["api_key_env"]))

    # ---- 2. 用户登记的任意服务（对外产品的核心：填 URL 就能接）----
    for it in _load_registry():
        k = it.get("key")
        if not k or k in seen:
            continue
        seen.add(k)
        clients.append(AIClient(k, it.get("name", k), "http", it.get("model", "unknown"),
                                it.get("note", ""), base_url=it.get("base_url"),
                                api_key=it.get("api_key"), api_key_env=it.get("api_key_env")))

    # ---- 3. 本地 CLI Agent ----
    codex = _find_codex()
    if codex:
        clients.append(AIClient("codex", "Codex CLI（本地 Agent）", "cli", "codex",
                                "OpenAI Codex CLI，读 ~/.codex/config.toml", exe=codex))
    claude = shutil.which("claude")
    if claude:
        clients.append(AIClient("claude", "Claude Code CLI（本地 Agent）", "cli", "claude",
                                "Anthropic Claude Code CLI", exe=claude))
    hermes = shutil.which("hermes")
    if hermes:
        clients.append(AIClient("hermes", "Hermes Agent（本机）", "cli", "hermes",
                                "Nous Research Hermes Agent", exe=hermes))

    # ---- 4. 平台自身端点（对外暴露，供别的 AI 来连）----
    clients.append(AIClient("platform", "本平台端点（OpenAI 兼容）", "platform",
                            "platform-semantic", "平台自带语义接口，无需任何外部 AI"))

    # ---- 5. 本地规则引擎（断网兜底）----
    clients.append(AIClient("local", "本地规则引擎（无 AI 兜底）", "local", "rule-based",
                            "不依赖任何外部 AI，确定性查询"))
    return clients


def list_clients():
    return [{"key": c.key, "name": c.name, "kind": c.kind, "model": c.model,
             "note": c.note, "available": c.available(),
             "base_url": c.base_url} for c in build_clients()]


_HARD_SYSTEM = (
    "你是数据分析助手，站在用户一问、平台一答的位置。"
    "规则：\n"
    "1. 仅根据【平台查询结果】中给出的真实数据作答,直接给出人话答案,可列点。\n"
    "2. 绝对禁止输出：代码、JSON、Markdown 代码块、SPARQL、数据结构、字段名列表。\n"
    "3. 绝对禁止输出思考过程、分析步骤、或对数据格式的说明。\n"
    "4. 结果含具体条目就概括成中文结论；结果为空就明确说'平台当前没查到'。\n"
    "5. 不编造、不猜测结果之外的数据。\n"
    "直接给最终答案文本，不要任何包装。"
)


def _harden_messages(messages, is_cli=False):
    """把数据问答消息统一成强约束版本，规避不同模型差异化输出(代码/不答)。"""
    out = []
    has_sys = False
    for m in messages or []:
        if m and m.get("role") == "system":
            has_sys = True
            if is_cli:
                # CLI 拼接时 system 内容会随用户消息一起进 prompt，去掉以复用 HARD
                continue
            out.append({"role": "system", "content": _HARD_SYSTEM})
        else:
            out.append(m)
    if not has_sys:
        out.insert(0, {"role": "system", "content": _HARD_SYSTEM})
    if is_cli:
        # CLI(codemer...) 无 system 槽位：把强约束作为首条用户指令
        out.insert(0, {"role": "user", "content": _HARD_SYSTEM})
    return out


def call_client(client_key, messages, timeout=120, max_tokens=600):
    """统一调用入口，返回 {content, backend, elapsed_ms, error}"""
    clients = {c.key: c for c in build_clients()}
    c = clients.get(client_key)
    if not c:
        return {"error": f"未找到 AI 客户端 {client_key}", "content": ""}

    t0 = time.time()
    try:
        if c.kind == "http":
            if not c.available():
                return {"error": f"{c.name} 缺少 API key（设置环境变量 {c.api_key_env} 或在界面登记）",
                        "content": "", "elapsed_ms": 0}
            r = requests.post(f"{c.base_url}/chat/completions",
                              headers={"Authorization": f"Bearer {c.api_key}",
                                       "Content-Type": "application/json"},
                              json={"model": c.model, "messages": _harden_messages(messages),
                                    "temperature": 0, "max_tokens": max_tokens},
                              timeout=timeout)
            r.raise_for_status()
            j = r.json()
            return {"content": j["choices"][0]["message"].get("content", ""),
                    "backend": j.get("model"), "elapsed_ms": int((time.time() - t0) * 1000)}

        if c.kind == "cli":
            prompt = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in _harden_messages(messages, is_cli=True))
            if c.key == "codex":
                cmd = [c.extra["exe"], "exec", "--skip-git-repo-check", prompt]
            elif c.key == "claude":
                cmd = [c.extra["exe"], "-p", prompt]
            else:
                cmd = [c.extra["exe"], "-z", prompt]
            pr = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                encoding="utf-8", errors="ignore", cwd=BASE)
            content = "\n".join(l for l in (pr.stdout or "").splitlines() if l.strip())
            err = None
            if "not logged in" in content.lower() or "please run /login" in content.lower():
                err = "CLI 未登录（需先执行登录）"
            return {"content": content, "backend": f"{c.key}-cli",
                    "elapsed_ms": int((time.time() - t0) * 1000), "error": err}

        if c.kind in ("local", "platform"):
            return {"content": "", "backend": "rule-based",
                    "elapsed_ms": int((time.time() - t0) * 1000),
                    "note": "该模式不生成自然语言，直接返回平台结构化查询结果"}
    except subprocess.TimeoutExpired:
        return {"error": f"{c.name} 超时", "content": "", "elapsed_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "content": "",
                "elapsed_ms": int((time.time() - t0) * 1000)}
    return {"error": "未知客户端类型", "content": ""}


if __name__ == "__main__":
    print(json.dumps(list_clients(), ensure_ascii=False, indent=1))
