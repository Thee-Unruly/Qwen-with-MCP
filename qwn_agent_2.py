#!/usr/bin/env python3
"""
qwen_agent_web.py — a small browser UI for the qwen_agent.py tool-using agent,
now with real MCP servers plugged in alongside the built-in tools.

Same agent loop as the terminal demo (qwen_agent.py) — same 5-step cap,
same streaming — just driven from a chat window instead of the command
line, and able to call out to any MCP server listed in mcp_config.json
in addition to (or instead of) the local Python functions.

Runs fully offline once the model and MCP servers are set up. No API key
needed for any of the default servers.

SETUP
    pip install -r requirements.txt
    Keep this file in the same folder as qwen_agent.py — it reuses its
    tools, schemas, and system prompt so the two demos never drift apart.

USAGE
    python qwen_agent_web.py
    python qwen_agent_web.py --model qwen3:4b --port 5050
    python qwen_agent_web.py --no-mcp        # local tools only
    Then open http://127.0.0.1:5000 in a browser.
"""

import argparse
import atexit
import json
import os

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from mcp_hub import MCPHub
from qwen_agent import (
    MAX_TOOL_ITERATIONS,
    MODEL_DEFAULT,
    SYSTEM_PROMPT,
    TOOL_FUNCTIONS,
    TOOL_SCHEMAS,
    check_ollama_installed,
    check_ollama_running_and_model,
)

MCP_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_config.json")

# Local tools that a connected "notes" MCP server would duplicate — if that
# server comes up, we drop these so the model isn't offered two near-identical
# ways to do the same thing. If it's not connected, these stay as a fallback.
NOTE_TOOL_NAMES = {"list_notes", "search_notes", "read_file"}

app = Flask(__name__)
STATE = {"model": MODEL_DEFAULT, "hub": None, "tool_schemas": TOOL_SCHEMAS}


def _get(obj, key, default=None):
    """Read a field from either a dict chunk or an SDK object chunk."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def build_tool_schemas(hub):
    """Combine the built-in tools with whatever the connected MCP servers
    offer, dropping local tools that an MCP server now covers."""
    local = TOOL_SCHEMAS
    if hub and hub.provides("notes"):
        local = [s for s in TOOL_SCHEMAS if s["function"]["name"] not in NOTE_TOOL_NAMES]
    mcp_schemas = hub.tool_schemas if hub else []
    return local + mcp_schemas


def dispatch_tool(name, args, hub):
    """Run a tool call against whichever backend owns it — a local Python
    function or a connected MCP server — and always return a string."""
    if hub and hub.is_mcp_tool(name):
        try:
            return hub.call_tool(name, args)
        except Exception as e:
            return f"Error calling MCP tool {name}: {e}"

    tool_fn = TOOL_FUNCTIONS.get(name)
    if tool_fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        return tool_fn(**args)
    except Exception as e:
        return f"Error running {name}: {e}"


def tool_origin(name, hub):
    """('mcp', server_name) or ('local', None) — for the UI to label chips."""
    if hub and hub.is_mcp_tool(name):
        server_name, _ = hub.tool_index[name]
        return "mcp", server_name
    return "local", None


def agent_stream(question, think):
    """Generator yielding one JSON event per line (NDJSON) for the browser."""
    import ollama

    hub = STATE["hub"]
    tool_schemas = STATE["tool_schemas"]

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
                tools=tool_schemas, think=think, stream=True,
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

            origin, server = tool_origin(name, hub)
            yield emit({"type": "tool_call", "name": name, "args": args, "origin": origin, "server": server})

            result = dispatch_tool(name, args, hub)

            yield emit({"type": "tool_result", "name": name, "text": str(result), "origin": origin, "server": server})
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
    parser.add_argument("--no-mcp", action="store_true", help="Disable MCP servers; use only local tools")
    args = parser.parse_args()

    STATE["model"] = args.model

    # Initialize MCP hub if enabled
    if not args.no_mcp:
        try:
            hub = MCPHub(config_path=MCP_CONFIG_PATH, enabled=True)
            STATE["hub"] = hub
            STATE["tool_schemas"] = build_tool_schemas(hub)
            atexit.register(hub.shutdown)
        except Exception as e:
            print(f"Warning: Failed to initialize MCP hub: {e}")
            print("Falling back to local tools only.")
            STATE["tool_schemas"] = build_tool_schemas(None)
    else:
        STATE["tool_schemas"] = build_tool_schemas(None)

    check_ollama_installed()
    check_ollama_running_and_model(args.model)

    print(f"\nQwen agent UI running — open http://{args.host}:{args.port} in a browser\n")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()