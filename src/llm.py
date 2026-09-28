"""
the single LLM access layer used by every script in this repository

Backends and the environment variables they read:
    gemini      GEMINI_API_KEY            (paper: reader gemini-3-flash-preview, generation gemini-3.1-pro-preview)
    openai      OPENAI_API_KEY            (paper: GPT-5.6 reader on the second suite)
    azure       AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
                                          (paper: GPT-5.4 realisation of the 56 suite and cross-model reader)
    dashscope   DASHSCOPE_API_KEY         (paper: Qwen3-32B cross-model reader)
    anthropic   ANTHROPIC_API_KEY ; groq  GROQ_API_KEY ; huggingface HF_TOKEN ; local  (transformers on GPU)
"""
from __future__ import annotations
import logging
import time
from typing import Dict, List

log = logging.getLogger(__name__)

_LLM_BACKEND: str = "dashscope"

_DEFAULT_MODELS = {
    "dashscope": "qwen2.5-72b-instruct",
    "azure": "gpt-4o",
    "local": "Qwen/Qwen2.5-7B-Instruct",
    "huggingface": "Qwen/Qwen2.5-72B-Instruct",
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-3-flash-preview",
    "openai": "gpt-5.6",
}

_LOCAL_MODEL = None
_LOCAL_TOKENIZER = None
_LOCAL_MODEL_NAME = None


def set_llm_backend(backend: str) -> None:
    global _LLM_BACKEND
    if backend not in _DEFAULT_MODELS:
        raise ValueError(f"Unknown backend '{backend}'. Choose from: {list(_DEFAULT_MODELS)}")
    _LLM_BACKEND = backend
    log.info(f"LLM backend set to: {backend} (default model: {_DEFAULT_MODELS[backend]})")


def call_llm(
    system: str,
    prompt: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    max_retries: int = 5,
) -> str:
    resolved_model = model or _DEFAULT_MODELS[_LLM_BACKEND]

    dispatch = {
        "dashscope": _call_dashscope,
        "azure": _call_azure,
        "local": _call_local,
        "huggingface": _call_huggingface,
        "groq": _call_groq,
        "anthropic": _call_anthropic,
        "gemini": _call_gemini,
        "openai": _call_openai,
    }
    fn = dispatch.get(_LLM_BACKEND)
    if fn is None:
        raise RuntimeError(f"Unknown LLM backend: {_LLM_BACKEND}")

    for attempt in range(max_retries):
        try:
            return fn(system, prompt, resolved_model, temperature, max_tokens)
        except Exception as e:
            err_str = str(e).lower()
            is_retryable = any(k in err_str for k in (
                "rate limit", "429", "503", "502", "timeout",
                "too many requests", "overloaded", "server error",
            ))
            if not is_retryable or attempt == max_retries - 1:
                raise
            wait = min(2 ** attempt * 5, 120)
            log.warning(f"  Retryable error (attempt {attempt+1}/{max_retries}), "
                        f"waiting {wait}s: {e}")
            time.sleep(wait)


def _call_dashscope(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    import os
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "openai package not installed. Install with: pip install openai\n"
            "Then set DASHSCOPE_API_KEY environment variable."
        )
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY env var not set")
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if "qwen3" in model.lower():
        kwargs["extra_body"] = {"enable_thinking": False}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _call_openai(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    import os
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY env var not set")
    client = OpenAI(api_key=api_key)
    is_reasoning = model.lower().startswith(("gpt-5", "o1", "o3", "o4"))
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    if is_reasoning:
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _call_azure(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    import os
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise RuntimeError(
            "openai package not installed. Install with: pip install openai"
        )
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not api_key or not endpoint:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT env vars must be set"
        )
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", model)
    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
    )

    model_lower = (deployment or model).lower()
    is_reasoning = (
        model_lower.startswith("gpt-5") or
        model_lower.startswith("o1") or
        model_lower.startswith("o3") or
        model_lower.startswith("o4")
    )

    kwargs = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "model": deployment,
    }
    if is_reasoning:
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _load_local_model(model_name: str) -> None:
    global _LOCAL_MODEL, _LOCAL_TOKENIZER, _LOCAL_MODEL_NAME
    if _LOCAL_MODEL is not None and _LOCAL_MODEL_NAME == model_name:
        return

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    log.info(f"Loading local model: {model_name} ...")

    _LOCAL_TOKENIZER = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, padding_side="left"
    )

    if torch.cuda.is_available():
        free_mem = []
        for i in range(torch.cuda.device_count()):
            free = torch.cuda.mem_get_info(i)[0] / 1e9
            free_mem.append((free, i))
            log.info(f"  GPU {i}: {free:.1f} GB free")

        best_free = max(f for f, _ in free_mem)

        model_lower = model_name.lower()
        est_gb = 140 if "72b" in model_lower or "70b" in model_lower else \
                 60 if "32b" in model_lower else \
                 28 if "14b" in model_lower else \
                 14 if "7b" in model_lower or "8b" in model_lower else 8

        best_gpu = max(free_mem, key=lambda x: x[0])[1]
        load_kwargs = {"trust_remote_code": True}

        if best_free >= est_gb * 1.1:
            load_kwargs["dtype"] = torch.float16
            load_kwargs["device_map"] = f"cuda:{best_gpu}"
            log.info(f"  Strategy: single GPU {best_gpu} in fp16 ({est_gb}GB model, {best_free:.0f}GB free)")
        else:
            try:
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                )
                load_kwargs["device_map"] = f"cuda:{best_gpu}"
                log.info(f"  Strategy: 4-bit NF4 on GPU {best_gpu} ({est_gb}GB fp16 model, "
                         f"{best_free:.0f}GB free, ~{est_gb // 4}GB quantized)")
            except ImportError:
                raise RuntimeError(
                    f"Model {model_name} too large for single GPU fp16 ({est_gb}GB needed, "
                    f"{best_free:.0f}GB free on best GPU) and bitsandbytes not installed. "
                    f"Install with: pip install bitsandbytes"
                )
    else:
        load_kwargs = {"trust_remote_code": True, "dtype": torch.float16, "device_map": "cpu"}
        log.info("  No GPU available, loading on CPU")

    _LOCAL_MODEL = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
    _LOCAL_MODEL.eval()
    _LOCAL_MODEL_NAME = model_name
    log.info(f"  Model loaded successfully")


def _call_local(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    import torch

    _load_local_model(model)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    text = _LOCAL_TOKENIZER.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    device = _LOCAL_MODEL.get_input_embeddings().weight.device
    inputs = _LOCAL_TOKENIZER(text, return_tensors="pt").to(device)

    gen_kwargs = {
        "max_new_tokens": max_tokens,
        "do_sample": temperature > 0,
        "eos_token_id": _LOCAL_TOKENIZER.eos_token_id,
        "pad_token_id": _LOCAL_TOKENIZER.eos_token_id,
        "repetition_penalty": 1.05,
    }
    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    with torch.no_grad():
        out = _LOCAL_MODEL.generate(**inputs, **gen_kwargs)

    new_tokens = out[0][inputs["input_ids"].shape[1]:]
    return _LOCAL_TOKENIZER.decode(new_tokens, skip_special_tokens=True).strip()


def _call_huggingface(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    import os
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise RuntimeError(
            "huggingface_hub package not installed. Install with: pip install huggingface_hub\n"
            "Then set HF_TOKEN environment variable."
        )
    client = InferenceClient(token=os.environ.get("HF_TOKEN"))
    response = client.chat_completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def _call_groq(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError(
            "groq package not installed. Install with: pip install groq\n"
            "Then set GROQ_API_KEY environment variable."
        )
    client = Groq()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def _call_anthropic(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Install with: pip install anthropic\n"
            "Then set ANTHROPIC_API_KEY environment variable."
        )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.content[0].text


def _call_gemini(
    system: str, prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed. Install with: pip install google-genai"
        )
    import os as _os
    api_key = _os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    thinking_cfg = None
    if "gemini-3" in model or "gemini-2.5" in model:
        thinking_cfg = types.ThinkingConfig(thinking_budget=1024)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            thinking_config=thinking_cfg,
        ),
    )
    return (response.text or "").strip()


def parse_dialogue(raw_text: str) -> List[Dict[str, str]]:
    turns = []
    current_role = None
    current_content = []

    role_map = {
        "[USER]": "user",
        "[ASST]": "assistant",
        "[TOOL_OUTPUT]": "tool_output",
    }

    for line in raw_text.strip().split("\n"):
        stripped = line.strip()

        matched_role = None
        for marker, role in role_map.items():
            if stripped.startswith(marker):
                matched_role = role
                content_after = stripped[len(marker):].strip()
                break

        if matched_role:
            if current_role is not None:
                turns.append({
                    "role": current_role,
                    "content": "\n".join(current_content).strip(),
                })
            current_role = matched_role
            current_content = [content_after] if content_after else []
        else:
            if current_role is not None:
                current_content.append(line.rstrip())

    if current_role is not None and current_content:
        turns.append({
            "role": current_role,
            "content": "\n".join(current_content).strip(),
        })

    return turns


