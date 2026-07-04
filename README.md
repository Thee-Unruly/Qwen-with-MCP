# Qwen Agent — Web UI

A browser chat window for the `qwen_agent.py` tool-using agent, for when you'd
rather demo it live than type commands on stage. Same agent loop, same tools,
same 5-step cap — it just streams into a chat page instead of a terminal.

## Setup

```bash
pip install -r requirements.txt
```

Also needs Ollama running locally with a tool-calling model pulled:

```bash
ollama pull qwen3:4b
```

## Run

```bash
python qwen_agent_web.py
```

Then open **http://127.0.0.1:5000** in a browser.

Options:

```bash
python qwen_agent_web.py --model qwen3:4b --port 5050 --host 0.0.0.0
```

## What you'll see

- Type a question, or click one of the three suggested prompts.
- Tick **Show thinking** to stream Qwen3's reasoning trace above the answer.
- Every tool call it makes shows up as an expandable chip — click one to see
  the exact arguments and the raw result it read back.

## Files

| File | Purpose |
|---|---|
| `qwen_agent.py` | The original CLI agent — tools, schemas, system prompt. The web UI imports from this so both demos always match. |
| `qwen_agent_web.py` | Flask app: streams the agent loop to the browser as NDJSON. |
| `templates/index.html` | Chat page markup. |
| `static/style.css` | Styling (matches the Build with Qwen deck palette). |
| `static/app.js` | Streams and renders events into the chat UI. |
| `sample_notes/` | The same three notes (budget, roadmap, meeting notes) the suggested prompts ask about. |

## Notes

- Everything runs locally against Ollama — no API key, no data leaving the machine.
- The CLI (`python qwen_agent.py "..."`) still works exactly as before; this is an additional interface, not a replacement.
