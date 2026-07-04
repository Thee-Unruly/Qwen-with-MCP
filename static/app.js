const chat = document.getElementById("chat");
const emptyState = document.getElementById("emptyState");
const composer = document.getElementById("composer");
const questionInput = document.getElementById("questionInput");
const thinkToggle = document.getElementById("thinkToggle");
const sendBtn = document.getElementById("sendBtn");
const statusDot = document.getElementById("statusDot");

const tplUser = document.getElementById("tpl-user");
const tplAssistant = document.getElementById("tpl-assistant");
const tplToolEvent = document.getElementById("tpl-tool-event");

document.querySelectorAll(".suggestion").forEach((btn) => {
  btn.addEventListener("click", () => {
    questionInput.value = btn.dataset.q;
    questionInput.focus();
  });
});

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;
  askAgent(question, thinkToggle.checked);
  questionInput.value = "";
});

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function addUserMessage(text) {
  if (emptyState) emptyState.remove();
  const node = tplUser.content.cloneNode(true);
  node.querySelector(".bubble").textContent = text;
  chat.appendChild(node);
  scrollToBottom();
}

function addAssistantMessage() {
  const node = tplAssistant.content.firstElementChild.cloneNode(true);
  chat.appendChild(node);
  scrollToBottom();
  return {
    root: node,
    thinkingDetails: node.querySelector(".thinking"),
    thinkingText: node.querySelector(".thinking-text"),
    toolEvents: node.querySelector(".tool-events"),
    bubble: node.querySelector(".bubble"),
  };
}

function addToolEvent(container, name, args) {
  const node = tplToolEvent.content.firstElementChild.cloneNode(true);
  node.querySelector(".tool-name").textContent = name + "(...)";
  node.querySelector(".tool-args").textContent = JSON.stringify(args, null, 2);
  container.appendChild(node);
  scrollToBottom();
  return {
    root: node,
    status: node.querySelector(".tool-status"),
    result: node.querySelector(".tool-result"),
  };
}

async function askAgent(question, think) {
  addUserMessage(question);
  const assistant = addAssistantMessage();
  sendBtn.disabled = true;
  statusDot.style.background = "#c98a54";

  let currentTool = null;

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, think }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop(); // last partial line stays in buffer

      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        handleEvent(assistant, event, (tool) => (currentTool = tool), () => currentTool);
      }
    }
  } catch (err) {
    assistant.bubble.innerHTML = `<span class="error-text">Something went wrong: ${escapeHtml(String(err))}</span>`;
  } finally {
    sendBtn.disabled = false;
    statusDot.style.background = "";
    scrollToBottom();
  }
}

function handleEvent(assistant, event, setTool, getTool) {
  switch (event.type) {
    case "thinking":
      assistant.thinkingDetails.hidden = false;
      assistant.thinkingText.textContent += event.text;
      break;

    case "content":
      assistant.bubble.textContent += event.text;
      break;

    case "tool_call": {
      const tool = addToolEvent(assistant.toolEvents, event.name, event.args);
      tool.root.open = true;
      setTool(tool);
      break;
    }

    case "tool_result": {
      const tool = getTool();
      if (tool) {
        tool.result.textContent = event.text;
        tool.status.textContent = "done";
        tool.status.classList.add("done");
        tool.root.open = false;
      }
      break;
    }

    case "error":
      assistant.bubble.innerHTML += `<span class="error-text">${escapeHtml(event.text)}</span>`;
      break;

    case "done":
      break;
  }
  scrollToBottom();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
