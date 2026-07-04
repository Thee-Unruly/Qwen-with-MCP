#!/usr/bin/env python3
"""
qwen_agent_web.py — a small browser UI for the qwen_agent.py tool-using agent.

Same agent loop as the terminal demo (qwen_agent.py) — same tools, same
system prompt, same 5-step cap — just driven from a chat window instead
of the command line. The page streams the model's thinking trace, tool
calls, and tool results live as they happen.

Runs fully offline once the model is downloaded. No API key needed.

SETUP
    pip install flask ollama
    Keep this file in the same folder as qwen_agent.py — it reuses its
    tools, schemas, and system prompt so the two demos never drift apart.

USAGE
    python qwen_agent_web.py
    python qwen_agent_web.py --model qwen3:4b --port 5050
    Then open http://127.0.0.1:5000 in a browser.
"""

import argparse
import json

from flask import Flask, Response, render_template, request, stream_with_context

from qwen_agent import (
    MAX_TOOL_ITERATIONS,
    MODEL_DEFAULT,
    SYSTEM_PROMPT,
    TOOL_FUNCTIONS,
    TOOL_SCHEMAS,
    check_ollama_installed,
    check_ollama_running_and_model,
)

app = Flask(__name__)
STATE = {"model": MODEL_DEFAULT}


def _get(obj, key, default=None):
    """Read a field from either a dict chunk or an SDK object chunk."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def agent_stream(question, think):
    """Generator yielding one JSON event per line (NDJSON) for the browser."""
    import ollama

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    def emit(event):
        return json.dumps(event) + "\n"

    for _ in range(MAX_TOOL_ITERATIONS):
        content_parts = []
        tool_calls = None

        try:
            stream = ollama.chat(
                model=STATE["model"], messages=messages,
                tools=TOOL_SCHEMAS, think=think, stream=True,
            )
            for chunk in stream:
                msg = _get(chunk, "message", {})
                thinking_piece = _get(msg, "thinking")
                content_piece = _get(msg, "content")
                tc = _get(msg, "tool_calls")

                if thinking_piece:
                    yield emit({"type": "thinking", "text": thinking_piece})
                if content_piece:
                    content_parts.append(content_piece)
                    yield emit({"type": "content", "text": content_piece})
                if tc:
                    tool_calls = tc
        except Exception as e:
            yield emit({"type": "error", "text": f"Couldn't reach Ollama: {e}"})
            return

        content = "".join(content_parts)

        if not tool_calls:
            yield emit({"type": "done"})
            return

        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for call in tool_calls:
            fn = _get(call, "function", {})
            name = _get(fn, "name")
            args = _get(fn, "arguments")
            if not isinstance(args, dict):
                args = {}

            yield emit({"type": "tool_call", "name": name, "args": args})

            tool_fn = TOOL_FUNCTIONS.get(name)
            if tool_fn is None:
                result = f"Error: unknown tool '{name}'"
            else:
                try:
                    result = tool_fn(**args)
                except Exception as e:
                    result = f"Error running {name}: {e}"

            yield emit({"type": "tool_result", "name": name, "text": str(result)})
            messages.append({"role": "tool", "content": str(result), "name": name})

    yield emit({"type": "error", "text": "Hit the max reasoning steps without a final answer."})


@app.route("/")
def index():
    return render_template("index.html", model=STATE["model"])


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    question = (data.get("question") or "").strip()
    think = bool(data.get("think"))

    if not question:
        return Response(json.dumps({"type": "error", "text": "Type a question first."}) + "\n",
                         mimetype="application/x-ndjson")

    return Response(stream_with_context(agent_stream(question, think)),
                     mimetype="application/x-ndjson")


def main():
    parser = argparse.ArgumentParser(description="Browser chat UI for the Qwen tool-using agent.")
    parser.add_argument("--model", default=MODEL_DEFAULT, help=f"Ollama model tag (default: {MODEL_DEFAULT})")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    STATE["model"] = args.model

    check_ollama_installed()
    check_ollama_running_and_model(args.model)

    print(f"\nQwen agent UI running — open http://{args.host}:{args.port} in a browser\n")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
