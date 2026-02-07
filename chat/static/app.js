/**
 * SelfAgent — Chat UI
 * WebSocket client with WhatsApp-style message rendering.
 */

(function () {
  "use strict";

  // ── DOM Elements ───────────────────────────────────
  var chatMessages = document.getElementById("chat-messages");
  var messageInput = document.getElementById("message-input");
  var sendBtn = document.getElementById("send-btn");
  var clearBtn = document.getElementById("clear-btn");
  var settingsBtn = document.getElementById("settings-btn");
  var settingsPanel = document.getElementById("settings-panel");
  var settingsClose = document.getElementById("settings-close");
  var settingsBackdrop = document.querySelector(".settings-backdrop");
  var saveSettingsBtn = document.getElementById("save-settings");
  var statusText = document.getElementById("status-text");
  var typingIndicator = document.getElementById("typing-indicator");
  var welcomeHint = document.getElementById("welcome-hint");
  var tokenDisplay = document.getElementById("token-display");

  var providerSelect = document.getElementById("provider-select");
  var keyOpenai = document.getElementById("key-openai");
  var keyAnthropic = document.getElementById("key-anthropic");
  var keyGoogle = document.getElementById("key-google");
  var keyOpenrouter = document.getElementById("key-openrouter");
  var modelSelect = document.getElementById("model-select");
  var tempInput = document.getElementById("temp-input");
  var tempValue = document.getElementById("temp-value");

  var providerKeyMap = {
    openai: keyOpenai,
    anthropic: keyAnthropic,
    google: keyGoogle,
    openrouter: keyOpenrouter,
  };

  var tasksBtn = document.getElementById("tasks-btn");
  var taskSidebar = document.getElementById("task-sidebar");
  var sidebarClose = document.getElementById("sidebar-close");

  var fileInput = document.getElementById("file-input");
  var attachBtn = document.getElementById("attach-btn");
  var filePreview = document.getElementById("file-preview");

  var toolsToggles = document.getElementById("tools-toggles");

  // ── State ──────────────────────────────────────────
  var ws = null;
  var reconnectTimer = null;
  var isWaiting = false;
  var pendingFiles = [];
  var sessionTokens = { input: 0, output: 0 };
  var lastMessageContent = "";  // Prevent duplicate messages

  // ── LocalStorage Settings ──────────────────────────
  function loadSettings() {
    var saved = localStorage.getItem("selfagent_settings");
    if (saved) {
      try {
        var s = JSON.parse(saved);

        // Migrate old format: single apiKey → per-provider key
        if (s.apiKey && !s.openai_key && !s.google_key && !s.openrouter_key) {
          console.log("Migrating old settings format to per-provider keys");
          var oldProvider = s.provider || "openai";
          if (oldProvider === "openai") s.openai_key = s.apiKey;
          else if (oldProvider === "anthropic") s.anthropic_key = s.apiKey;
          else if (oldProvider === "google") s.google_key = s.apiKey;
          else if (oldProvider === "openrouter") s.openrouter_key = s.apiKey;
          delete s.apiKey;
          localStorage.setItem("selfagent_settings", JSON.stringify(s));
        }

        providerSelect.value = s.provider || "openai";
        // Load per-provider keys
        keyOpenai.value = s.openai_key || "";
        keyAnthropic.value = s.anthropic_key || "";
        keyGoogle.value = s.google_key || "";
        keyOpenrouter.value = s.openrouter_key || "";
        modelSelect.value = s.model || "gpt-4o";
        tempInput.value = s.temperature != null ? s.temperature : 0.7;
        tempValue.textContent = tempInput.value;
        highlightActiveKey();
        return s;
      } catch (e) { /* ignore */ }
    }
    return null;
  }

  function saveSettings() {
    var provider = providerSelect.value;
    var activeKey = (providerKeyMap[provider] || {}).value || "";
    var s = {
      provider: provider,
      openai_key: keyOpenai.value,
      anthropic_key: keyAnthropic.value,
      google_key: keyGoogle.value,
      openrouter_key: keyOpenrouter.value,
      model: modelSelect.value,
      temperature: parseFloat(tempInput.value),
    };
    localStorage.setItem("selfagent_settings", JSON.stringify(s));
    return s;
  }

  function highlightActiveKey() {
    var provider = providerSelect.value;
    document.querySelectorAll(".api-key-row").forEach(function (row) {
      if (row.getAttribute("data-provider") === provider) {
        row.classList.add("active");
      } else {
        row.classList.remove("active");
      }
    });
  }

  function sendConfigToServer(settings) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    var configPayload = {
      type: "config",
      config: {
        model: {
          provider: settings.provider,
          openai_key: settings.openai_key || "",
          anthropic_key: settings.anthropic_key || "",
          google_key: settings.google_key || "",
          openrouter_key: settings.openrouter_key || "",
          model_name: settings.model,
          temperature: settings.temperature,
        },
      },
    };
    console.log("Sending config:", JSON.stringify(configPayload.config.model));
    ws.send(JSON.stringify(configPayload));
  }

  function getActiveKey(settings) {
    var keyMap = {
      openai: settings.openai_key,
      anthropic: settings.anthropic_key,
      google: settings.google_key,
      openrouter: settings.openrouter_key,
    };
    return keyMap[settings.provider] || "";
  }

  // ── Token Display + Cost ────────────────────────────
  // Pricing per 1M tokens (USD) — approximate, updated 2025
  var MODEL_PRICING = {
    // OpenAI
    "gpt-4o":           { input: 2.50, output: 10.00 },
    "gpt-4o-mini":      { input: 0.15, output: 0.60 },
    // Anthropic
    "claude-sonnet-4-20250514": { input: 3.00, output: 15.00 },
    "claude-opus-4-20250514":   { input: 15.00, output: 75.00 },
    // Google
    "gemini-2.0-flash":  { input: 0.10, output: 0.40 },
    "gemini-2.5-flash":  { input: 0.15, output: 0.60 },
    "gemini-2.5-pro":    { input: 1.25, output: 10.00 },
  };

  var sessionCost = 0;
  var lastModel = "";

  function updateTokenDisplay(data) {
    var meta = data.metadata || {};
    var prevInput = sessionTokens.input;
    var prevOutput = sessionTokens.output;
    sessionTokens.input = meta.total_input_tokens || sessionTokens.input;
    sessionTokens.output = meta.total_output_tokens || sessionTokens.output;
    var total = sessionTokens.input + sessionTokens.output;

    // Track model for cost calculation
    if (meta.model) lastModel = meta.model;

    // Calculate cost for this request's tokens
    var newInput = sessionTokens.input - prevInput;
    var newOutput = sessionTokens.output - prevOutput;
    var pricing = MODEL_PRICING[lastModel];
    if (pricing && (newInput > 0 || newOutput > 0)) {
      sessionCost += (newInput / 1000000) * pricing.input +
                     (newOutput / 1000000) * pricing.output;
    }

    if (total > 0) {
      var costStr = sessionCost > 0 ? " (~$" + sessionCost.toFixed(4) + ")" : "";
      tokenDisplay.textContent = formatTokens(total) + " tokens" + costStr;
      tokenDisplay.title =
        "Input: " + formatTokens(sessionTokens.input) +
        " | Output: " + formatTokens(sessionTokens.output) +
        " | Total: " + formatTokens(total) +
        (sessionCost > 0 ? "\nEstimated cost: $" + sessionCost.toFixed(4) : "") +
        (lastModel ? "\nModel: " + lastModel : "");
    }
  }

  function formatTokens(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "k";
    return String(n);
  }

  // ── WebSocket ──────────────────────────────────────
  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var url = proto + "//" + location.host + "/ws";

    ws = new WebSocket(url);

    ws.onopen = function () {
      statusText.textContent = "Online";
      statusText.style.color = "#00a884";
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      // Send saved settings on connect
      var settings = loadSettings();
      if (settings) {
        var activeKey = getActiveKey(settings);
        if (activeKey) {
          sendConfigToServer(settings);
          welcomeHint.textContent = "Send a message to get started.";
        }
      }
      // Request tools list for settings
      ws.send(JSON.stringify({ type: "get_tools" }));
    };

    ws.onmessage = function (event) {
      var data = JSON.parse(event.data);
      handleServerMessage(data);
    };

    ws.onclose = function () {
      statusText.textContent = "Disconnected";
      statusText.style.color = "#f15c6d";
      hideTyping();
      isWaiting = false;
      updateSendButton();
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = function () {
      // onclose will fire after this
    };
  }

  function handleServerMessage(data) {
    switch (data.type) {
      case "message":
        hideTyping();
        // Skip duplicate consecutive messages
        if (data.content === lastMessageContent && data.role === "assistant") {
          break;
        }
        lastMessageContent = data.content;
        addMessage(data.content, data.role || "assistant");
        if (data.role === "assistant") {
          isWaiting = false;
          updateSendButton();
        }
        break;

      case "typing":
        showTyping("Agent is thinking...");
        break;

      case "status":
        showTyping(data.content || "Agent is working...");
        break;

      case "tool_result":
        // Tool results are intermediate — keep typing indicator
        break;

      case "usage":
        updateTokenDisplay(data);
        break;

      case "tools_list":
        renderToolToggles(data.metadata && data.metadata.tools ? data.metadata.tools : []);
        break;

      case "error":
        hideTyping();
        addStatusMessage(data.content, true);
        isWaiting = false;
        updateSendButton();
        break;

      case "done":
        hideTyping();
        isWaiting = false;
        lastMessageContent = "";
        updateSendButton();
        break;

      default:
        break;
    }
  }

  // ── Message Rendering ──────────────────────────────
  function addMessage(content, role) {
    removeWelcome();

    var div = document.createElement("div");
    div.className = "message " + role;

    var contentEl = document.createElement("span");
    contentEl.className = "content";
    contentEl.innerHTML = renderMarkdown(content);

    var ts = document.createElement("span");
    ts.className = "timestamp";
    ts.textContent = formatTime(new Date());

    div.appendChild(contentEl);
    div.appendChild(ts);
    chatMessages.appendChild(div);
    scrollToBottom();
  }

  function addStatusMessage(content, isError) {
    var div = document.createElement("div");
    div.className = "status-message" + (isError ? " error" : "");
    div.textContent = content;
    chatMessages.appendChild(div);
    scrollToBottom();
  }

  function removeWelcome() {
    var w = chatMessages.querySelector(".welcome-message");
    if (w) w.remove();
  }

  function renderMarkdown(text) {
    if (!text) return "";
    // Escape HTML
    var html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Code blocks (```...```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
      return '<pre><code>' + code.trim() + '</code></pre>';
    });

    // Inline code (`...`)
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Bold (**...**)
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    // Italic (*...*)
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

    // Image paths — detect screenshot/image references
    html = html.replace(
      /((?:\/[\w.\-]+)+\.(?:png|jpg|jpeg|gif|webp|svg))/gi,
      '<img src="file://$1" alt="image" onerror="this.style.display=\'none\'">'
    );

    return html;
  }

  function formatTime(date) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function scrollToBottom() {
    requestAnimationFrame(function () {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  }

  // ── Typing Indicator ──────────────────────────────
  function showTyping(text) {
    var textEl = typingIndicator.querySelector(".typing-text");
    if (textEl) textEl.textContent = text || "Agent is working...";
    typingIndicator.classList.remove("hidden");
    scrollToBottom();
  }

  function hideTyping() {
    typingIndicator.classList.add("hidden");
  }

  // ── File Attachment ─────────────────────────────────
  fileInput.addEventListener("change", function () {
    var files = Array.from(fileInput.files || []);
    files.forEach(function (f) { pendingFiles.push(f); });
    renderFilePreview();
    fileInput.value = "";
  });

  function renderFilePreview() {
    filePreview.innerHTML = "";
    if (pendingFiles.length === 0) {
      filePreview.classList.add("hidden");
      return;
    }
    filePreview.classList.remove("hidden");
    pendingFiles.forEach(function (f, i) {
      var chip = document.createElement("div");
      chip.className = "file-chip";
      chip.innerHTML =
        '<span>' + escapeHtml(f.name) + '</span>' +
        '<button data-idx="' + i + '">&times;</button>';
      chip.querySelector("button").addEventListener("click", function () {
        pendingFiles.splice(i, 1);
        renderFilePreview();
      });
      filePreview.appendChild(chip);
    });
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ── Send Message ───────────────────────────────────
  function sendMessage() {
    var text = messageInput.value.trim();
    if (!text || isWaiting) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    // Upload pending files and include paths in the message
    if (pendingFiles.length > 0) {
      var fileInfo = [];
      var uploads = pendingFiles.map(function (f) {
        var fd = new FormData();
        fd.append("file", f);
        return fetch("/upload", { method: "POST", body: fd })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            fileInfo.push(f.name + " -> " + data.path);
          })
          .catch(function () {
            fileInfo.push(f.name + " (upload failed)");
          });
      });
      Promise.all(uploads).then(function () {
        text += "\n\n[Attached files uploaded to: " + fileInfo.join(", ") + "]";
        pendingFiles = [];
        renderFilePreview();
        doSend(text);
      });
      return;
    }

    doSend(text);
  }

  function doSend(text) {
    addMessage(text, "user");

    ws.send(
      JSON.stringify({
        type: "message",
        content: text,
        timestamp: new Date().toISOString(),
      })
    );

    messageInput.value = "";
    messageInput.style.height = "auto";
    isWaiting = true;
    updateSendButton();
  }

  function updateSendButton() {
    sendBtn.disabled = isWaiting;
  }

  // ── Auto-resize Textarea ──────────────────────────
  messageInput.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 120) + "px";
  });

  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener("click", sendMessage);

  // ── Drag & Drop File Upload ─────────────────────────
  chatMessages.addEventListener("dragover", function (e) {
    e.preventDefault();
    chatMessages.classList.add("drag-over");
  });
  chatMessages.addEventListener("dragleave", function () {
    chatMessages.classList.remove("drag-over");
  });
  chatMessages.addEventListener("drop", function (e) {
    e.preventDefault();
    chatMessages.classList.remove("drag-over");
    var files = Array.from(e.dataTransfer.files || []);
    files.forEach(function (f) { pendingFiles.push(f); });
    renderFilePreview();
  });

  // ── Clear Conversation ─────────────────────────────
  clearBtn.addEventListener("click", function () {
    if (!confirm("Clear the conversation?")) return;
    chatMessages.innerHTML = "";
    sessionTokens = { input: 0, output: 0 };
    tokenDisplay.textContent = "";
    tokenDisplay.title = "";
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "clear" }));
    }
  });

  // ── Task Sidebar ──────────────────────────────────
  tasksBtn.addEventListener("click", function () {
    taskSidebar.classList.toggle("hidden");
  });

  sidebarClose.addEventListener("click", function () {
    taskSidebar.classList.add("hidden");
  });

  // ── Settings Panel ─────────────────────────────────
  settingsBtn.addEventListener("click", function () {
    settingsPanel.classList.remove("hidden");
    // Request fresh tools list
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "get_tools" }));
    }
  });

  function closeSettings() {
    settingsPanel.classList.add("hidden");
  }

  settingsClose.addEventListener("click", closeSettings);
  settingsBackdrop.addEventListener("click", closeSettings);

  // ── Settings Tabs ─────────────────────────────────
  var tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var tab = btn.getAttribute("data-tab");
      tabBtns.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      document.querySelectorAll(".tab-content").forEach(function (tc) {
        tc.classList.remove("active");
      });
      var target = document.getElementById("tab-" + tab);
      if (target) target.classList.add("active");
    });
  });

  // ── Tool Toggles ─────────────────────────────────
  function renderToolToggles(tools) {
    if (!tools || tools.length === 0) {
      toolsToggles.innerHTML = '<p class="sidebar-empty">No tools loaded</p>';
      return;
    }
    toolsToggles.innerHTML = "";
    tools.forEach(function (tool) {
      var row = document.createElement("div");
      row.className = "tool-toggle";
      row.innerHTML =
        '<div class="tool-toggle-info">' +
          '<div class="tool-toggle-name">' + escapeHtml(tool.name) + '</div>' +
          '<div class="tool-toggle-desc">' + escapeHtml(tool.description || "") + '</div>' +
        '</div>' +
        '<label class="toggle-switch">' +
          '<input type="checkbox" ' + (tool.enabled ? "checked" : "") + ' data-tool="' + escapeHtml(tool.name) + '">' +
          '<span class="toggle-slider"></span>' +
        '</label>';
      row.querySelector("input").addEventListener("change", function () {
        var toolName = this.getAttribute("data-tool");
        var enabled = this.checked;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "toggle_tool",
            tool_name: toolName,
            enabled: enabled,
          }));
        }
      });
      toolsToggles.appendChild(row);
    });
  }

  // ── Provider/Model Filtering ────────────────────
  var providerGroupMap = {
    openai: ["openai-models"],
    anthropic: ["anthropic-models"],
    google: ["google-models"],
    openrouter: ["openrouter-models", "openrouter-paid-models"],
  };

  function filterModels() {
    var provider = providerSelect.value;
    var groups = providerGroupMap[provider] || [];
    var allGroups = modelSelect.querySelectorAll("optgroup");
    allGroups.forEach(function (g) {
      g.style.display = "none";
      var opts = g.querySelectorAll("option");
      opts.forEach(function (o) { o.disabled = true; });
    });
    var firstOption = null;
    groups.forEach(function (id) {
      var g = document.getElementById(id);
      if (g) {
        g.style.display = "";
        var opts = g.querySelectorAll("option");
        opts.forEach(function (o) { o.disabled = false; });
        if (!firstOption && opts.length > 0) firstOption = opts[0];
      }
    });
    var current = modelSelect.querySelector('option[value="' + modelSelect.value + '"]');
    if (!current || current.disabled) {
      if (firstOption) modelSelect.value = firstOption.value;
    }
  }

  providerSelect.addEventListener("change", function () {
    filterModels();
    highlightActiveKey();
  });
  filterModels();
  highlightActiveKey();

  tempInput.addEventListener("input", function () {
    tempValue.textContent = this.value;
  });

  saveSettingsBtn.addEventListener("click", function () {
    var settings = saveSettings();
    sendConfigToServer(settings);
    closeSettings();
    addStatusMessage("Settings saved.", false);
    if (getActiveKey(settings)) {
      welcomeHint.textContent = "Send a message to get started.";
    }
  });

  // ── Init ───────────────────────────────────────────
  loadSettings();
  filterModels();
  // Re-apply saved model after filtering
  var savedSettings = localStorage.getItem("selfagent_settings");
  if (savedSettings) {
    try {
      var s = JSON.parse(savedSettings);
      if (s.model) modelSelect.value = s.model;
    } catch (e) { /* ignore */ }
  }
  connect();
})();
