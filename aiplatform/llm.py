# -*- coding: utf-8 -*-
"""
多 AI 模型适配层 —— 平台的「AI 无关」证明
同一套工具（MCP / 平台工具），不同厂商的 LLM 都能驱动。
"""
import os, json, re
import requests

CALL_LOGS = []  # 记录最近一次调用，用于界面展示


class LLMProvider:
    """OpenAI 兼容的通用 provider"""
    def __init__(self, name, base_url, api_key, models, note=""):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.models = models
        self.note = note

    def available(self):
        return bool(self.api_key)

    def chat(self, model, messages, temperature=0, max_tokens=600, timeout=60):
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            timeout=timeout,
        )
        r.raise_for_status()
        j = r.json()
        return {
            "content": j["choices"][0]["message"].get("content") or "",
            "backend": j.get("model"),
            "usage": j.get("usage", {}),
        }


def get_providers():
    """平台内置 + 可扩展的 AI 供应商列表"""
    provs = []
    ecnu_key = os.environ.get("CHATECNU-API-KEY")
    if ecnu_key:
        provs.append(LLMProvider(
            "华东师大开放平台 (ChatECNU)",
            "https://chat.ecnu.edu.cn/open/api/v1",
            ecnu_key,
            models=["ecnu-max", "ecnu-plus"],
            note="站内直连 · 后端 ecnu-max=DeepSeek, ecnu-plus=Qwen",
        ))
    # 预留：任何 OpenAI 兼容服务只要配环境变量即可接入
    for env, name, url, models in [
        ("DEEPSEEK_API_KEY", "DeepSeek 官方", "https://api.deepseek.com/v1", ["deepseek-chat"]),
        ("DASHSCOPE_API_KEY", "阿里通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", ["qwen-plus"]),
        ("OPENAI_API_KEY", "OpenAI", "https://api.openai.com/v1", ["gpt-4o-mini"]),
    ]:
        k = os.environ.get(env)
        if k:
            provs.append(LLMProvider(name, url, k, models=models, note=f"env {env}"))
    return provs


def list_models():
    out = []
    for p in get_providers():
        for m in p.models:
            out.append({"provider": p.name, "model": m, "note": p.note})
    return out


def call_model(provider_name, model, messages, **kw):
    for p in get_providers():
        if p.name == provider_name or model in p.models:
            return p.chat(model, messages, **kw)
    # 兜底：任意名字都试 ChatECNU
    for p in get_providers():
        return p.chat(model, messages, **kw)
    return {"content": "", "backend": None, "usage": {}}


if __name__ == "__main__":
    print(json.dumps(list_models(), ensure_ascii=False, indent=1))
