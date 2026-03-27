from __future__ import annotations

import json
import os
import urllib.request

import ollama

from talky.prompting import build_llm_system_prompt


class OllamaTextCleaner:
    def __init__(self, model_name: str, debug_stream: bool = False) -> None:
        self.model_name = model_name
        self.debug_stream = debug_stream
        # Module-level ollama.chat uses a Client created at import time (localhost only).
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self._ollama_client = ollama.Client(host=host)

    def warm_up(self) -> None:
        self._chat_with_fallback(
            messages=[{"role": "user", "content": "ping"}],
            think=False,
            stream=False,
            options={"temperature": 0.0, "num_predict": 8, "top_p": 0.1},
        )

    def clean(self, raw_text: str, dictionary_terms: list[str], custom_prompt_template: str = "") -> str:
        system_prompt = build_llm_system_prompt(dictionary_terms, custom_template=custom_prompt_template)
        stream = self._chat_with_fallback(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            think=False,
            stream=True,
            options={
                "temperature": 0,
                "num_predict": 300,
                "top_p": 0.1,
            },
        )
        parts: list[str] = []
        thinking_parts: list[str] = []
        for chunk in stream:
            message = chunk.get("message", {})
            piece = message.get("content", "") or ""
            thinking_piece = message.get("thinking", "") or ""
            if thinking_piece:
                if self.debug_stream:
                    print(thinking_piece, end="", flush=True)
                thinking_parts.append(thinking_piece)
            if piece:
                if self.debug_stream:
                    print(piece, end="", flush=True)
                parts.append(piece)
        if self.debug_stream:
            print()
        final = "".join(parts).strip()
        if final:
            return final
        # Never surface model thinking as final content.
        # If content stream is empty, preserve the source transcript instead.
        return raw_text.strip()

    def _chat_with_fallback(self, messages, think: bool, stream: bool, options: dict):
        try:
            return self._ollama_client.chat(
                model=self.model_name,
                messages=messages,
                think=think,
                stream=stream,
                options=options,
                keep_alive="1h",
            )
        except Exception as exc:
            print(f"[Talky][debug] SDK chat failed, fallback to HTTP /api/chat: {exc}")
            return self._chat_via_http(
                messages=messages,
                think=think,
                stream=stream,
                options=options,
            )

    def _chat_via_http(self, messages, think: bool, stream: bool, options: dict):
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        url = f"{host}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "think": think,
            "stream": False,
            "options": options,
            "keep_alive": "1h",
        }
        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))

        if stream:
            content = str(data.get("message", {}).get("content", "") or "")
            return [{"message": {"content": content, "thinking": ""}}]
        return data
