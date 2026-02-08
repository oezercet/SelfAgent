/**
 * SelfAgent — Settings panel
 * Load/save settings, provider/model filtering, config sync, tabs.
 * Exposes functions on window.SA namespace.
 */

(function () {
  "use strict";

  var SA = window.SA = window.SA || {};

  // ── DOM refs used by settings ──────────────────────
  var providerSelect = document.getElementById("provider-select");
  var keyOpenai = document.getElementById("key-openai");
  var keyAnthropic = document.getElementById("key-anthropic");
  var keyGoogle = document.getElementById("key-google");
  var keyOpenrouter = document.getElementById("key-openrouter");
  var modelSelect = document.getElementById("model-select");
  var tempInput = document.getElementById("temp-input");
  var tempValue = document.getElementById("temp-value");

  var ollamaBaseUrl = document.getElementById("ollama-base-url");

  var providerKeyMap = {
    openai: keyOpenai,
    anthropic: keyAnthropic,
    google: keyGoogle,
    openrouter: keyOpenrouter,
    ollama: ollamaBaseUrl,
  };

  // ── Highlight Active API Key Row ───────────────────
  SA.highlightActiveKey = function () {
    var provider = providerSelect.value;
    document.querySelectorAll(".api-key-row").forEach(function (row) {
      if (row.getAttribute("data-provider") === provider) {
        row.classList.add("active");
      } else {
        row.classList.remove("active");
      }
    });
  };

  // ── Load Settings from localStorage ────────────────
  SA.loadSettings = function () {
    var saved = localStorage.getItem("selfagent_settings");
    if (saved) {
      try {
        var s = JSON.parse(saved);

        // Migrate old format: single apiKey -> per-provider key
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
        ollamaBaseUrl.value = s.ollama_base_url || "http://localhost:11434";
        modelSelect.value = s.model || "gpt-4o";
        tempInput.value = s.temperature != null ? s.temperature : 0.7;
        tempValue.textContent = tempInput.value;
        SA.highlightActiveKey();
        return s;
      } catch (e) { /* ignore */ }
    }
    return null;
  };

  // ── Save Settings to localStorage ──────────────────
  SA.saveSettings = function () {
    var provider = providerSelect.value;
    var s = {
      provider: provider,
      openai_key: keyOpenai.value,
      anthropic_key: keyAnthropic.value,
      google_key: keyGoogle.value,
      openrouter_key: keyOpenrouter.value,
      ollama_base_url: ollamaBaseUrl.value || "http://localhost:11434",
      model: modelSelect.value,
      temperature: parseFloat(tempInput.value),
    };
    localStorage.setItem("selfagent_settings", JSON.stringify(s));
    return s;
  };

  // ── Send Config to Server via WebSocket ────────────
  SA.sendConfigToServer = function (settings) {
    if (!SA.ws || SA.ws.readyState !== WebSocket.OPEN) return;
    var configPayload = {
      type: "config",
      config: {
        model: {
          provider: settings.provider,
          openai_key: settings.openai_key || "",
          anthropic_key: settings.anthropic_key || "",
          google_key: settings.google_key || "",
          openrouter_key: settings.openrouter_key || "",
          ollama_base_url: settings.ollama_base_url || "http://localhost:11434",
          model_name: settings.model,
          temperature: settings.temperature,
        },
      },
    };
    console.log("Sending config:", JSON.stringify(configPayload.config.model));
    SA.ws.send(JSON.stringify(configPayload));
  };

  // ── Get Active API Key ─────────────────────────────
  SA.getActiveKey = function (settings) {
    if (settings.provider === "ollama") return "ollama";
    var keyMap = {
      openai: settings.openai_key,
      anthropic: settings.anthropic_key,
      google: settings.google_key,
      openrouter: settings.openrouter_key,
    };
    return keyMap[settings.provider] || "";
  };

  // ── Provider/Model Filtering ────────────────────
  var providerGroupMap = {
    openai: ["openai-models"],
    anthropic: ["anthropic-models"],
    google: ["google-models"],
    openrouter: ["openrouter-models", "openrouter-paid-models"],
    ollama: ["ollama-models"],
  };

  SA.filterModels = function () {
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
  };

  // ── Settings Panel open/close ──────────────────────
  var settingsPanel = document.getElementById("settings-panel");
  var settingsClose = document.getElementById("settings-close");
  var settingsBackdrop = document.querySelector(".settings-backdrop");
  var settingsBtn = document.getElementById("settings-btn");
  var saveSettingsBtn = document.getElementById("save-settings");
  var welcomeHint = document.getElementById("welcome-hint");

  SA.closeSettings = function () {
    settingsPanel.classList.add("hidden");
  };

  settingsBtn.addEventListener("click", function () {
    settingsPanel.classList.remove("hidden");
    // Request fresh tools list
    if (SA.ws && SA.ws.readyState === WebSocket.OPEN) {
      SA.ws.send(JSON.stringify({ type: "get_tools" }));
    }
  });

  settingsClose.addEventListener("click", SA.closeSettings);
  settingsBackdrop.addEventListener("click", SA.closeSettings);

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

  // ── Ollama Status & Pull ─────────────────────────────
  var ollamaSection = document.getElementById("ollama-status-section");
  var ollamaStatusDot = document.getElementById("ollama-status-dot");
  var ollamaStatusText = document.getElementById("ollama-status-text");
  var ollamaCheckBtn = document.getElementById("ollama-check-btn");
  var ollamaModelsList = document.getElementById("ollama-models-list");
  var ollamaInstalledModels = document.getElementById("ollama-installed-models");
  var ollamaPullInput = document.getElementById("ollama-pull-input");
  var ollamaPullBtn = document.getElementById("ollama-pull-btn");
  var ollamaPullProgress = document.getElementById("ollama-pull-progress");
  var ollamaProgressFill = document.getElementById("ollama-progress-fill");
  var ollamaProgressText = document.getElementById("ollama-progress-text");

  function showOllamaSection() {
    if (providerSelect.value === "ollama") {
      ollamaSection.classList.remove("hidden");
      checkOllamaStatus();
    } else {
      ollamaSection.classList.add("hidden");
    }
  }

  function checkOllamaStatus() {
    if (!SA.ws || SA.ws.readyState !== WebSocket.OPEN) return;
    ollamaStatusText.textContent = "Checking...";
    SA.ws.send(JSON.stringify({ type: "check_ollama" }));
  }

  SA.handleOllamaStatus = function (data) {
    var meta = data.metadata || {};
    if (meta.status === "running") {
      ollamaStatusDot.className = "status-dot online";
      ollamaStatusText.textContent = "Running (" + meta.url + ")";
      // Show installed models
      var models = meta.models || [];
      if (models.length > 0) {
        ollamaModelsList.classList.remove("hidden");
        ollamaInstalledModels.innerHTML = "";
        models.forEach(function (name) {
          var chip = document.createElement("span");
          chip.className = "model-chip";
          chip.textContent = name;
          ollamaInstalledModels.appendChild(chip);
        });
        // Add dynamic models to select
        var optgroup = document.getElementById("ollama-models");
        if (optgroup) {
          var existing = {};
          optgroup.querySelectorAll("option").forEach(function (o) { existing[o.value] = true; });
          models.forEach(function (name) {
            if (!existing[name]) {
              var opt = document.createElement("option");
              opt.value = name;
              opt.textContent = name;
              optgroup.appendChild(opt);
            }
          });
        }
      } else {
        ollamaModelsList.classList.add("hidden");
      }
    } else if (meta.status === "not_running") {
      ollamaStatusDot.className = "status-dot offline";
      ollamaStatusText.textContent = "Not running";
      ollamaModelsList.classList.add("hidden");
    } else {
      ollamaStatusDot.className = "status-dot offline";
      ollamaStatusText.textContent = "Error";
      ollamaModelsList.classList.add("hidden");
    }
  };

  SA.handleOllamaPullProgress = function (data) {
    var meta = data.metadata || {};
    ollamaPullProgress.classList.remove("hidden");
    ollamaProgressFill.style.width = (meta.progress || 0) + "%";
    ollamaProgressText.textContent = data.content || ("Pulling... " + (meta.progress || 0) + "%");
    ollamaPullBtn.disabled = true;
  };

  SA.handleOllamaPullDone = function (data) {
    ollamaProgressFill.style.width = "100%";
    ollamaProgressText.textContent = data.content || "Done!";
    ollamaPullBtn.disabled = false;
    // Refresh status to update model list
    setTimeout(function () {
      ollamaPullProgress.classList.add("hidden");
      checkOllamaStatus();
    }, 1500);
  };

  ollamaCheckBtn.addEventListener("click", checkOllamaStatus);

  ollamaPullBtn.addEventListener("click", function () {
    var model = ollamaPullInput.value.trim();
    if (!model) return;
    if (!SA.ws || SA.ws.readyState !== WebSocket.OPEN) return;
    SA.ws.send(JSON.stringify({ type: "pull_ollama", model: model }));
  });

  // ── Provider Change Handler ────────────────────────
  providerSelect.addEventListener("change", function () {
    SA.filterModels();
    SA.highlightActiveKey();
    showOllamaSection();
  });

  // Show/hide on init
  showOllamaSection();

  // ── Temperature Slider ─────────────────────────────
  tempInput.addEventListener("input", function () {
    tempValue.textContent = this.value;
  });

  // ── Save Settings Button ───────────────────────────
  saveSettingsBtn.addEventListener("click", function () {
    var settings = SA.saveSettings();
    SA.sendConfigToServer(settings);
    SA.closeSettings();
    SA.addStatusMessage("Settings saved.", false);
    if (SA.getActiveKey(settings)) {
      welcomeHint.textContent = "Send a message to get started.";
    }
  });
})();
