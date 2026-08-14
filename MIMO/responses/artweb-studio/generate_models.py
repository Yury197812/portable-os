"""Deterministic seed generator: ~400-model catalog for ArtWeb Studio.
FREE is a subset; tool_use is first-class; no fixed 29-model cap.
"""
import json, random
from pathlib import Path

random.seed(20260814)

FAMILIES = [
    ("GPT-4o", "OpenAI", ["tool_use", "vision", "reasoning", "safety"], "text"),
    ("GPT-4o-mini", "OpenAI", ["tool_use", "vision", "web"], "text"),
    ("o1", "OpenAI", ["reasoning", "code"], "text"),
    ("Claude", "Anthropic", ["tool_use", "vision", "safety"], "text"),
    ("Claude-Haiku", "Anthropic", ["tool_use", "vision"], "text"),
    ("Gemini", "Google", ["tool_use", "vision", "audio", "web"], "text"),
    ("Gemini-Flash", "Google", ["tool_use", "vision", "audio"], "text"),
    ("Llama", "Meta", ["tool_use", "reasoning"], "text"),
    ("Qwen", "Alibaba", ["tool_use", "code"], "text"),
    ("DeepSeek", "DeepSeek", ["tool_use", "code", "reasoning"], "text"),
    ("Mistral", "Mistral", ["tool_use", "code"], "text"),
    ("Mixtral", "Mistral", ["tool_use"], "text"),
    ("Codestral", "Mistral", ["code", "tool_use"], "text"),
    ("Groq-Llama", "Groq", ["tool_use", "speed"], "text"),
    ("Groq-Mixtral", "Groq", ["tool_use", "speed"], "text"),
    ("Phi", "Microsoft", ["reasoning"], "text"),
    ("Gemma", "Google", ["tool_use"], "text"),
    ("Command-R", "Cohere", ["tool_use", "web"], "text"),
    ("Sonar", "Perplexity", ["web", "tool_use"], "text"),
    ("Titan", "AWS", ["safety"], "text"),
    ("Nova", "AWS", ["tool_use", "vision"], "text"),
    ("Yi", "01.AI", ["tool_use", "code"], "text"),
    ("GLM", "Zhipu", ["tool_use", "vision"], "text"),
    ("ERNIE", "Baidu", ["tool_use", "web"], "text"),
    ("LLaVA", "Open Community", ["vision"], "text"),
    ("Stable-Code", "Stability", ["code"], "text"),
    ("Jamba", "AI21", ["tool_use"], "text"),
    ("Ministral", "Mistral", ["tool_use"], "text"),
    ("Grok", "xAI", ["web", "reasoning"], "text"),
    ("C4AI-Command", "Cohere", ["tool_use", "web"], "text"),
    ("Palmyra", "Writer", ["tool_use"], "text"),
    ("Hermes", "Nous Research", ["tool_use", "reasoning"], "text"),
    ("Neural-Chat", "Intel", ["tool_use"], "text"),
    ("OpenChat", "OpenChat", ["tool_use"], "text"),
    ("Zephyr", "HuggingFace", ["tool_use"], "text"),
    ("Whisper", "OpenAI", ["audio"], "audio"),
    ("SDXL", "Stability", ["vision"], "image"),
    ("DALL-E", "OpenAI", ["vision", "safety"], "image"),
    ("Embed", "Cohere", [], "embed"),
    ("Titan-Embed", "AWS", [], "embed"),
]

SIZES = ["", "-mini", "-small", "-8B", "-70B", "-turbo", "-pro", "-ultra", "-Q4", "-Q8"]
models = []
for fam, prov, caps, mod in FAMILIES:
    for i, sz in enumerate(SIZES):
        free = i % 3 == 0 and mod == "text"
        caps_final = list(caps)
        if free and "free" not in caps_final:
            caps_final.append("free")
        models.append({
            "id": f"{fam.lower().replace(' ', '-')}{sz.lower() or ''}",
            "name": f"{fam}{sz}",
            "provider": prov,
            "family": fam,
            "capabilities": caps_final,
            "free": free,
            "tool_use": "tool_use" in caps_final,
            "quality": round(random.uniform(4.0, 9.6), 1),
            "latency_ms": random.randint(60, 2500),
            "cost_per_mtok": 0.0 if free else round(random.uniform(0.05, 15.0), 2),
            "context_k": random.choice([0, 8, 16, 32, 64, 128, 256, 1000, 2000]),
            "modality": mod,
            "locality": random.choice(["cloud", "local", "hybrid"]),
            "privacy": random.randint(3, 9),
            "availability": random.randint(6, 10),
        })

out = Path(__file__).parent / "models.seed.json"
out.write_text(json.dumps(models, ensure_ascii=False, indent=1), encoding="utf-8")
print("generated", len(models), "models ->", out)
