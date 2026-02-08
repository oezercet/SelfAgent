/**
 * SelfAgent — UI helpers
 * Message rendering, typing indicators, file preview, tool toggles, tokens.
 * Exposes functions on window.SA namespace.
 */

(function () {
  "use strict";

  var SA = window.SA = window.SA || {};

  // ── Token Display + Cost ────────────────────────────
  // Pricing per 1M tokens (USD) — approximate, updated 2025
  SA.MODEL_PRICING = {
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

  SA.sessionCost = 0;
  SA.lastModel = "";

  // ── Escape HTML ─────────────────────────────────────
  SA.escapeHtml = function (str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  };

  // ── Markdown Rendering ──────────────────────────────
  SA.renderMarkdown = function (text) {
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

    // Headings (###, ##, #)
    html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

    // Horizontal rule
    html = html.replace(/^---+$/gm, "<hr>");

    // Links [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // Unordered lists (- item or * item)
    html = html.replace(/^(?:[-*]) (.+)$/gm, "<li>$1</li>");
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");

    // Ordered lists (1. item)
    html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
    // Wrap consecutive <li> not already in <ul> into <ol>
    html = html.replace(/(<li>(?:(?!<\/?[uo]l>).)*<\/li>\n?)+/g, function (match) {
      if (match.indexOf("<ul>") === -1 && match.indexOf("<ol>") === -1) {
        return "<ol>" + match + "</ol>";
      }
      return match;
    });

    // Blockquotes (> text)
    html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");

    // Paragraphs — double newline
    html = html.replace(/\n\n+/g, "</p><p>");
    html = "<p>" + html + "</p>";
    // Clean up empty paragraphs and paragraphs around block elements
    html = html.replace(/<p><\/p>/g, "");
    html = html.replace(/<p>(<(?:h[1-4]|pre|ul|ol|hr|blockquote))/g, "$1");
    html = html.replace(/(<\/(?:h[1-4]|pre|ul|ol|blockquote)>)<\/p>/g, "$1");
    html = html.replace(/<p>(<hr>)<\/p>/g, "$1");

    // Image paths — detect screenshot/image references
    html = html.replace(
      /((?:\/[\w.\-]+)+\.(?:png|jpg|jpeg|gif|webp|svg))/gi,
      '<img src="file://$1" alt="image" onerror="this.style.display=\'none\'">'
    );

    return html;
  };

  // ── Time Formatting ─────────────────────────────────
  SA.formatTime = function (date) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  SA.formatTokens = function (n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "k";
    return String(n);
  };

  // ── Scroll ──────────────────────────────────────────
  SA.scrollToBottom = function () {
    var chatMessages = document.getElementById("chat-messages");
    requestAnimationFrame(function () {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  };

  // ── Remove Welcome ──────────────────────────────────
  SA.removeWelcome = function () {
    var chatMessages = document.getElementById("chat-messages");
    var w = chatMessages.querySelector(".welcome-message");
    if (w) w.remove();
  };

  // ── Message Rendering ──────────────────────────────
  SA.addMessage = function (content, role) {
    var chatMessages = document.getElementById("chat-messages");
    SA.removeWelcome();

    var div = document.createElement("div");
    div.className = "message " + role;

    var contentEl = document.createElement("span");
    contentEl.className = "content";
    contentEl.innerHTML = SA.renderMarkdown(content);

    var ts = document.createElement("span");
    ts.className = "timestamp";
    ts.textContent = SA.formatTime(new Date());

    div.appendChild(contentEl);
    div.appendChild(ts);
    chatMessages.appendChild(div);
    SA.scrollToBottom();
  };

  SA.addStatusMessage = function (content, isError) {
    var chatMessages = document.getElementById("chat-messages");
    var div = document.createElement("div");
    div.className = "status-message" + (isError ? " error" : "");
    div.textContent = content;
    chatMessages.appendChild(div);
    SA.scrollToBottom();
  };

  // ── Typing Indicator ──────────────────────────────
  SA.showTyping = function (text) {
    var typingIndicator = document.getElementById("typing-indicator");
    var textEl = typingIndicator.querySelector(".typing-text");
    if (textEl) textEl.textContent = text || "Agent is working...";
    typingIndicator.classList.remove("hidden");
    SA.scrollToBottom();
  };

  SA.hideTyping = function () {
    var typingIndicator = document.getElementById("typing-indicator");
    typingIndicator.classList.add("hidden");
  };

  // ── File Preview ──────────────────────────────────
  SA.renderFilePreview = function () {
    var filePreview = document.getElementById("file-preview");
    filePreview.innerHTML = "";
    if (SA.pendingFiles.length === 0) {
      filePreview.classList.add("hidden");
      return;
    }
    filePreview.classList.remove("hidden");
    SA.pendingFiles.forEach(function (f, i) {
      var chip = document.createElement("div");
      chip.className = "file-chip";
      chip.innerHTML =
        '<span>' + SA.escapeHtml(f.name) + '</span>' +
        '<button data-idx="' + i + '">&times;</button>';
      chip.querySelector("button").addEventListener("click", function () {
        SA.pendingFiles.splice(i, 1);
        SA.renderFilePreview();
      });
      filePreview.appendChild(chip);
    });
  };

  // ── Token Display ──────────────────────────────────
  SA.updateTokenDisplay = function (data) {
    var tokenDisplay = document.getElementById("token-display");
    var meta = data.metadata || {};
    var prevInput = SA.sessionTokens.input;
    var prevOutput = SA.sessionTokens.output;
    SA.sessionTokens.input = meta.total_input_tokens || SA.sessionTokens.input;
    SA.sessionTokens.output = meta.total_output_tokens || SA.sessionTokens.output;
    var total = SA.sessionTokens.input + SA.sessionTokens.output;

    // Track model for cost calculation
    if (meta.model) SA.lastModel = meta.model;

    // Calculate cost for this request's tokens
    var newInput = SA.sessionTokens.input - prevInput;
    var newOutput = SA.sessionTokens.output - prevOutput;
    var pricing = SA.MODEL_PRICING[SA.lastModel];
    if (pricing && (newInput > 0 || newOutput > 0)) {
      SA.sessionCost += (newInput / 1000000) * pricing.input +
                        (newOutput / 1000000) * pricing.output;
    }

    if (total > 0) {
      var costStr = SA.sessionCost > 0 ? " (~$" + SA.sessionCost.toFixed(4) + ")" : "";
      tokenDisplay.textContent = SA.formatTokens(total) + " tokens" + costStr;
      tokenDisplay.title =
        "Input: " + SA.formatTokens(SA.sessionTokens.input) +
        " | Output: " + SA.formatTokens(SA.sessionTokens.output) +
        " | Total: " + SA.formatTokens(total) +
        (SA.sessionCost > 0 ? "\nEstimated cost: $" + SA.sessionCost.toFixed(4) : "") +
        (SA.lastModel ? "\nModel: " + SA.lastModel : "");
    }
  };

  // ── Tool Toggles ─────────────────────────────────
  SA.renderToolToggles = function (tools) {
    var toolsToggles = document.getElementById("tools-toggles");
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
          '<div class="tool-toggle-name">' + SA.escapeHtml(tool.name) + '</div>' +
          '<div class="tool-toggle-desc">' + SA.escapeHtml(tool.description || "") + '</div>' +
        '</div>' +
        '<label class="toggle-switch">' +
          '<input type="checkbox" ' + (tool.enabled ? "checked" : "") + ' data-tool="' + SA.escapeHtml(tool.name) + '">' +
          '<span class="toggle-slider"></span>' +
        '</label>';
      row.querySelector("input").addEventListener("change", function () {
        var toolName = this.getAttribute("data-tool");
        var enabled = this.checked;
        if (SA.ws && SA.ws.readyState === WebSocket.OPEN) {
          SA.ws.send(JSON.stringify({
            type: "toggle_tool",
            tool_name: toolName,
            enabled: enabled,
          }));
        }
      });
      toolsToggles.appendChild(row);
    });
  };
})();
