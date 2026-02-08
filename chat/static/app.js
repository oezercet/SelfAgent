/**
 * SelfAgent — Chat UI (Core)
 * DOM refs, state, WebSocket connect/handleServerMessage, sendMessage, init.
 * Uses window.SA namespace shared with ui.js and settings.js.
 */
(function () {
  "use strict";

  var SA = window.SA = window.SA || {};

  // ── DOM Elements ──
  var chatMessages = document.getElementById("chat-messages");
  var messageInput = document.getElementById("message-input");
  var sendBtn      = document.getElementById("send-btn");
  var clearBtn     = document.getElementById("clear-btn");
  var statusText   = document.getElementById("status-text");
  var tokenDisplay = document.getElementById("token-display");
  var welcomeHint  = document.getElementById("welcome-hint");
  var tasksBtn     = document.getElementById("tasks-btn");
  var taskSidebar  = document.getElementById("task-sidebar");
  var sidebarClose = document.getElementById("sidebar-close");
  var fileInput    = document.getElementById("file-input");
  var pinOverlay   = document.getElementById("pin-overlay");
  var pinInput     = document.getElementById("pin-input");
  var pinSubmit    = document.getElementById("pin-submit");
  var pinError     = document.getElementById("pin-error");

  // ── State ──
  SA.ws = null;
  var reconnectTimer = null;
  var isWaiting = false;
  SA.pendingFiles = [];
  SA.sessionTokens = { input: 0, output: 0 };
  var lastMessageContent = "";
  var authenticated = true;

  // ── WebSocket ──
  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    SA.ws = new WebSocket(proto + "//" + location.host + "/ws");

    SA.ws.onopen = function () {
      statusText.textContent = "Online";
      statusText.style.color = "#00a884";
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
      var settings = SA.loadSettings();
      if (settings) {
        if (SA.getActiveKey(settings)) {
          SA.sendConfigToServer(settings);
          welcomeHint.textContent = "Send a message to get started.";
        }
      }
      SA.ws.send(JSON.stringify({ type: "get_tools" }));
    };

    SA.ws.onmessage = function (event) {
      handleServerMessage(JSON.parse(event.data));
    };

    SA.ws.onclose = function () {
      statusText.textContent = "Disconnected";
      statusText.style.color = "#f15c6d";
      SA.hideTyping();
      isWaiting = false;
      updateSendButton();
      reconnectTimer = setTimeout(connect, 3000);
    };

    SA.ws.onerror = function () { /* onclose will fire */ };
  }

  function handleServerMessage(data) {
    switch (data.type) {
      case "message":
        SA.hideTyping();
        if (data.content === lastMessageContent && data.role === "assistant") break;
        lastMessageContent = data.content;
        SA.addMessage(data.content, data.role || "assistant");
        if (data.role === "assistant") { isWaiting = false; updateSendButton(); }
        break;

      case "typing":
        SA.showTyping("Agent is thinking...");
        break;

      case "status":
        SA.showTyping(data.content || "Agent is working...");
        break;

      case "tool_result":
        break;

      case "usage":
        SA.updateTokenDisplay(data);
        break;

      case "tools_list":
        SA.renderToolToggles(data.metadata && data.metadata.tools ? data.metadata.tools : []);
        break;

      case "error":
        SA.hideTyping();
        SA.addStatusMessage(data.content, true);
        isWaiting = false;
        updateSendButton();
        break;

      case "done":
        SA.hideTyping();
        isWaiting = false;
        lastMessageContent = "";
        updateSendButton();
        break;

      case "ollama_status":
        if (SA.handleOllamaStatus) SA.handleOllamaStatus(data);
        break;

      case "ollama_pull_progress":
        if (SA.handleOllamaPullProgress) SA.handleOllamaPullProgress(data);
        break;

      case "ollama_pull_done":
        if (SA.handleOllamaPullDone) SA.handleOllamaPullDone(data);
        break;

      case "auth_required":
        authenticated = false;
        if (pinOverlay) pinOverlay.classList.remove("hidden");
        break;

      case "auth_success":
        authenticated = true;
        if (pinOverlay) pinOverlay.classList.add("hidden");
        if (pinError) pinError.textContent = "";
        var s = SA.loadSettings();
        if (s) SA.sendConfigToServer(s);
        SA.ws.send(JSON.stringify({ type: "get_tools" }));
        break;

      case "auth_failed":
        if (pinError) pinError.textContent = "Wrong PIN. Try again.";
        if (pinInput) { pinInput.value = ""; pinInput.focus(); }
        break;
    }
  }

  // ── Send Message ──
  function sendMessage() {
    var text = messageInput.value.trim();
    if (!text || isWaiting) return;
    if (!SA.ws || SA.ws.readyState !== WebSocket.OPEN) return;

    if (SA.pendingFiles.length > 0) {
      var fileInfo = [];
      var uploads = SA.pendingFiles.map(function (f) {
        var fd = new FormData();
        fd.append("file", f);
        return fetch("/upload", { method: "POST", body: fd })
          .then(function (r) { return r.json(); })
          .then(function (d) { fileInfo.push(f.name + " -> " + d.path); })
          .catch(function () { fileInfo.push(f.name + " (upload failed)"); });
      });
      Promise.all(uploads).then(function () {
        text += "\n\n[Attached files uploaded to: " + fileInfo.join(", ") + "]";
        SA.pendingFiles = [];
        SA.renderFilePreview();
        doSend(text);
      });
      return;
    }
    doSend(text);
  }

  function doSend(text) {
    SA.addMessage(text, "user");
    SA.ws.send(JSON.stringify({
      type: "message", content: text, timestamp: new Date().toISOString(),
    }));
    messageInput.value = "";
    messageInput.style.height = "auto";
    isWaiting = true;
    updateSendButton();
  }

  function updateSendButton() { sendBtn.disabled = isWaiting; }

  // ── Auto-resize Textarea ──
  messageInput.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 120) + "px";
  });
  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  sendBtn.addEventListener("click", sendMessage);

  // ── File Input ──
  fileInput.addEventListener("change", function () {
    Array.from(fileInput.files || []).forEach(function (f) { SA.pendingFiles.push(f); });
    SA.renderFilePreview();
    fileInput.value = "";
  });

  // ── Drag & Drop ──
  chatMessages.addEventListener("dragover", function (e) {
    e.preventDefault(); chatMessages.classList.add("drag-over");
  });
  chatMessages.addEventListener("dragleave", function () {
    chatMessages.classList.remove("drag-over");
  });
  chatMessages.addEventListener("drop", function (e) {
    e.preventDefault(); chatMessages.classList.remove("drag-over");
    Array.from(e.dataTransfer.files || []).forEach(function (f) { SA.pendingFiles.push(f); });
    SA.renderFilePreview();
  });

  // ── Clear Conversation ──
  clearBtn.addEventListener("click", function () {
    if (!confirm("Clear the conversation?")) return;
    chatMessages.innerHTML = "";
    SA.sessionTokens = { input: 0, output: 0 };
    tokenDisplay.textContent = "";
    tokenDisplay.title = "";
    if (SA.ws && SA.ws.readyState === WebSocket.OPEN) {
      SA.ws.send(JSON.stringify({ type: "clear" }));
    }
  });

  // ── Task Sidebar ──
  tasksBtn.addEventListener("click", function () { taskSidebar.classList.toggle("hidden"); });
  sidebarClose.addEventListener("click", function () { taskSidebar.classList.add("hidden"); });

  // ── PIN Auth ──
  if (pinSubmit) {
    pinSubmit.addEventListener("click", function () {
      var pin = pinInput ? pinInput.value.trim() : "";
      if (!pin) return;
      if (SA.ws && SA.ws.readyState === WebSocket.OPEN) {
        SA.ws.send(JSON.stringify({ type: "auth", pin: pin }));
      }
    });
  }
  if (pinInput) {
    pinInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); if (pinSubmit) pinSubmit.click(); }
    });
  }

  // ── Init ──
  SA.loadSettings();
  SA.filterModels();
  SA.highlightActiveKey();
  var savedSettings = localStorage.getItem("selfagent_settings");
  if (savedSettings) {
    try {
      var parsed = JSON.parse(savedSettings);
      if (parsed.model) document.getElementById("model-select").value = parsed.model;
    } catch (e) { /* ignore */ }
  }
  connect();
})();
