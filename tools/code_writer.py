"""Code writer tool — write, run, debug code and manage packages.

Supports any language installed on the system. Executes code safely
with timeouts and output capture.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)

HOME_DIR = Path.home()

# Map language to execution command
RUNNERS = {
    "python": "python3",
    "python3": "python3",
    "javascript": "node",
    "js": "node",
    "node": "node",
    "typescript": "npx ts-node",
    "ts": "npx ts-node",
    "bash": "bash",
    "sh": "sh",
    "ruby": "ruby",
    "php": "php",
    "go": "go run",
    "rust": "rustc -o /tmp/selfagent_rust_out",  # compile step
    "java": "java",
    "perl": "perl",
}

EXTENSIONS = {
    "python": ".py",
    "python3": ".py",
    "javascript": ".js",
    "js": ".js",
    "node": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "bash": ".sh",
    "sh": ".sh",
    "ruby": ".rb",
    "php": ".php",
    "go": ".go",
    "rust": ".rs",
    "java": ".java",
    "perl": ".pl",
    "html": ".html",
    "css": ".css",
}

PACKAGE_MANAGERS = {
    "pip": "pip install",
    "pip3": "pip3 install",
    "npm": "npm install",
    "yarn": "yarn add",
    "brew": "brew install",
    "gem": "gem install",
    "cargo": "cargo add",
}


class CodeWriterTool(BaseTool):
    """Write, run, and debug code in any language."""

    name = "code_writer"
    description = (
        "Write code to files, execute scripts, debug errors, install packages, "
        "and create project scaffolds. Supports Python, JavaScript, TypeScript, "
        "Bash, Ruby, PHP, Go, Rust, and more."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "write_code",
                    "run_code",
                    "run_inline",
                    "debug_code",
                    "install_package",
                    "create_project",
                ],
                "description": "The code action to perform",
            },
            "language": {
                "type": "string",
                "description": "Programming language (python, javascript, bash, etc.)",
            },
            "code": {
                "type": "string",
                "description": "Source code (for write_code, run_inline)",
            },
            "file_path": {
                "type": "string",
                "description": "File path (for write_code, run_code)",
            },
            "package_name": {
                "type": "string",
                "description": "Package to install (for install_package)",
            },
            "manager": {
                "type": "string",
                "description": "Package manager: pip, npm, yarn, brew (for install_package)",
            },
            "project_name": {
                "type": "string",
                "description": "Project name (for create_project)",
            },
            "project_type": {
                "type": "string",
                "description": "Template: python-script, python-api, html-site, node-api, react-app, wordpress-theme, chrome-extension",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "write_code":
                return self._write_code(
                    kwargs.get("file_path", ""),
                    kwargs.get("code", ""),
                    kwargs.get("language", ""),
                )
            elif action == "run_code":
                return await self._run_code(kwargs.get("file_path", ""))
            elif action == "run_inline":
                return await self._run_inline(
                    kwargs.get("language", "python"),
                    kwargs.get("code", ""),
                )
            elif action == "debug_code":
                return await self._run_code(kwargs.get("file_path", ""))
            elif action == "install_package":
                return await self._install_package(
                    kwargs.get("package_name", ""),
                    kwargs.get("manager", "pip"),
                )
            elif action == "create_project":
                return self._create_project(
                    kwargs.get("project_name", ""),
                    kwargs.get("project_type", "python-script"),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Code writer failed: %s", action)
            return f"Error: {e}"

    def _write_code(self, file_path: str, code: str, language: str) -> str:
        if not file_path:
            return "Error: file_path is required."
        if not code:
            return "Error: code is required."

        path = Path(file_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")

        # Make shell scripts executable
        if language in ("bash", "sh") or path.suffix in (".sh", ".bash"):
            os.chmod(path, 0o755)

        return f"Written {len(code)} chars to {path}"

    async def _run_code(self, file_path: str) -> str:
        if not file_path:
            return "Error: file_path is required."

        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"File not found: {path}"

        # Detect language from extension
        ext = path.suffix.lower()
        lang_map = {v: k for k, v in EXTENSIONS.items()}
        language = lang_map.get(ext, "")
        runner = RUNNERS.get(language)

        if not runner:
            return f"Don't know how to run {ext} files. Supported: {', '.join(set(EXTENSIONS.values()))}"

        cmd = f"{runner} {path}"

        return await self._execute_command(cmd, cwd=str(path.parent))

    async def _run_inline(self, language: str, code: str) -> str:
        if not code:
            return "Error: code is required."

        language = language.lower()

        if language in ("python", "python3"):
            cmd = f"python3 -c {self._shell_quote(code)}"
        elif language in ("javascript", "js", "node"):
            cmd = f"node -e {self._shell_quote(code)}"
        elif language in ("bash", "sh"):
            cmd = f"bash -c {self._shell_quote(code)}"
        elif language == "ruby":
            cmd = f"ruby -e {self._shell_quote(code)}"
        elif language == "php":
            cmd = f"php -r {self._shell_quote(code)}"
        elif language == "perl":
            cmd = f"perl -e {self._shell_quote(code)}"
        else:
            return f"Inline execution not supported for '{language}'. Write to a file first."

        return await self._execute_command(cmd)

    async def _install_package(self, package: str, manager: str) -> str:
        if not package:
            return "Error: package_name is required."

        manager = manager.lower()
        cmd_prefix = PACKAGE_MANAGERS.get(manager)
        if not cmd_prefix:
            return f"Unknown package manager: {manager}. Supported: {', '.join(PACKAGE_MANAGERS.keys())}"

        cmd = f"{cmd_prefix} {package}"
        return await self._execute_command(cmd, timeout=120)

    def _create_project(self, name: str, project_type: str) -> str:
        if not name:
            return "Error: project_name is required."

        base = HOME_DIR / name
        if base.exists():
            return f"Directory already exists: {base}"

        project_type = project_type.lower()

        if project_type == "python-script":
            return self._scaffold_python_script(base, name)
        elif project_type == "python-api":
            return self._scaffold_python_api(base, name)
        elif project_type == "html-site":
            return self._scaffold_html_site(base, name)
        elif project_type == "node-api":
            return self._scaffold_node_api(base, name)
        elif project_type == "react-app":
            return self._scaffold_react_app(base, name)
        elif project_type == "wordpress-theme":
            return self._scaffold_wordpress_theme(base, name)
        elif project_type == "chrome-extension":
            return self._scaffold_chrome_extension(base, name)
        else:
            return (
                f"Unknown template: {project_type}. Available: "
                "python-script, python-api, html-site, node-api, "
                "react-app, wordpress-theme, chrome-extension"
            )

    # ── Scaffolds ────────────────────────────────────

    def _scaffold_python_script(self, base: Path, name: str) -> str:
        base.mkdir(parents=True)
        (base / "main.py").write_text(
            f'"""{{name}} — Main script."""\n\nimport argparse\n\n\n'
            f'def main():\n    parser = argparse.ArgumentParser(description="{name}")\n'
            f'    args = parser.parse_args()\n    print("Hello from {name}!")\n\n\n'
            f'if __name__ == "__main__":\n    main()\n',
            encoding="utf-8",
        )
        (base / "requirements.txt").write_text("", encoding="utf-8")
        (base / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        return f"Created Python script project at {base}"

    def _scaffold_python_api(self, base: Path, name: str) -> str:
        base.mkdir(parents=True)
        (base / "app.py").write_text(
            'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n'
            '@app.get("/")\ndef root():\n    return {"message": "Hello World"}\n\n\n'
            '@app.get("/health")\ndef health():\n    return {"status": "ok"}\n',
            encoding="utf-8",
        )
        (base / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
        (base / "README.md").write_text(
            f"# {name}\n\n```bash\npip install -r requirements.txt\nuvicorn app:app --reload\n```\n",
            encoding="utf-8",
        )
        return f"Created FastAPI project at {base}"

    def _scaffold_html_site(self, base: Path, name: str) -> str:
        base.mkdir(parents=True)
        (base / "index.html").write_text(
            f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            f'    <meta charset="UTF-8">\n'
            f'    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'    <title>{name}</title>\n    <link rel="stylesheet" href="style.css">\n'
            f'</head>\n<body>\n    <h1>{name}</h1>\n'
            f'    <script src="app.js"></script>\n</body>\n</html>\n',
            encoding="utf-8",
        )
        (base / "style.css").write_text(
            "* { margin: 0; padding: 0; box-sizing: border-box; }\n"
            "body { font-family: system-ui, sans-serif; padding: 2rem; }\n",
            encoding="utf-8",
        )
        (base / "app.js").write_text(
            f'console.log("{name} loaded");\n', encoding="utf-8"
        )
        return f"Created HTML site at {base}"

    def _scaffold_node_api(self, base: Path, name: str) -> str:
        base.mkdir(parents=True)
        (base / "index.js").write_text(
            'const express = require("express");\n'
            "const app = express();\n"
            "const PORT = process.env.PORT || 3000;\n\n"
            'app.use(express.json());\n\n'
            'app.get("/", (req, res) => res.json({ message: "Hello World" }));\n'
            'app.get("/health", (req, res) => res.json({ status: "ok" }));\n\n'
            "app.listen(PORT, () => console.log(`Server running on port ${PORT}`));\n",
            encoding="utf-8",
        )
        (base / "package.json").write_text(
            f'{{\n  "name": "{name}",\n  "version": "1.0.0",\n'
            f'  "main": "index.js",\n  "scripts": {{\n    "start": "node index.js"\n  }},\n'
            f'  "dependencies": {{\n    "express": "^4.18.0"\n  }}\n}}\n',
            encoding="utf-8",
        )
        (base / "README.md").write_text(
            f"# {name}\n\n```bash\nnpm install\nnpm start\n```\n",
            encoding="utf-8",
        )
        return f"Created Node.js API project at {base}"

    def _scaffold_react_app(self, base: Path, name: str) -> str:
        base.mkdir(parents=True)
        src = base / "src"
        src.mkdir()
        public = base / "public"
        public.mkdir()

        (base / "package.json").write_text(
            f'{{\n  "name": "{name}",\n  "version": "1.0.0",\n  "private": true,\n'
            f'  "type": "module",\n'
            f'  "scripts": {{\n    "dev": "vite",\n    "build": "vite build",\n    "preview": "vite preview"\n  }},\n'
            f'  "dependencies": {{\n    "react": "^18.2.0",\n    "react-dom": "^18.2.0"\n  }},\n'
            f'  "devDependencies": {{\n    "@vitejs/plugin-react": "^4.0.0",\n    "vite": "^5.0.0"\n  }}\n}}\n',
            encoding="utf-8",
        )
        (base / "vite.config.js").write_text(
            'import { defineConfig } from "vite";\nimport react from "@vitejs/plugin-react";\n\n'
            "export default defineConfig({\n  plugins: [react()],\n});\n",
            encoding="utf-8",
        )
        (base / "index.html").write_text(
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8" />\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            f'  <title>{name}</title>\n</head>\n<body>\n  <div id="root"></div>\n'
            '  <script type="module" src="/src/main.jsx"></script>\n</body>\n</html>\n',
            encoding="utf-8",
        )
        (src / "main.jsx").write_text(
            'import React from "react";\nimport ReactDOM from "react-dom/client";\n'
            'import App from "./App";\nimport "./index.css";\n\n'
            'ReactDOM.createRoot(document.getElementById("root")).render(\n'
            "  <React.StrictMode>\n    <App />\n  </React.StrictMode>\n);\n",
            encoding="utf-8",
        )
        (src / "App.jsx").write_text(
            f'function App() {{\n  return (\n    <div>\n      <h1>{name}</h1>\n'
            f'      <p>Edit src/App.jsx to get started.</p>\n    </div>\n  );\n}}\n\n'
            f"export default App;\n",
            encoding="utf-8",
        )
        (src / "index.css").write_text(
            ":root { font-family: system-ui, sans-serif; }\n"
            "body { margin: 0; padding: 2rem; }\n",
            encoding="utf-8",
        )
        (base / "README.md").write_text(
            f"# {name}\n\n```bash\nnpm install\nnpm run dev\n```\n",
            encoding="utf-8",
        )
        return f"Created React (Vite) project at {base}"

    def _scaffold_wordpress_theme(self, base: Path, name: str) -> str:
        slug = name.lower().replace(" ", "-")
        base.mkdir(parents=True)

        (base / "style.css").write_text(
            f"/*\n Theme Name: {name}\n Theme URI: \n Author: \n"
            f" Description: Custom WordPress theme\n Version: 1.0.0\n"
            f" Text Domain: {slug}\n*/\n\n"
            "body { font-family: system-ui, sans-serif; margin: 0; }\n"
            ".container { max-width: 1200px; margin: 0 auto; padding: 1rem; }\n",
            encoding="utf-8",
        )
        (base / "index.php").write_text(
            "<?php get_header(); ?>\n\n<main class=\"container\">\n"
            "  <?php if (have_posts()) : while (have_posts()) : the_post(); ?>\n"
            "    <article>\n      <h2><a href=\"<?php the_permalink(); ?>\">"
            "<?php the_title(); ?></a></h2>\n"
            "      <?php the_excerpt(); ?>\n    </article>\n"
            "  <?php endwhile; endif; ?>\n</main>\n\n<?php get_footer(); ?>\n",
            encoding="utf-8",
        )
        (base / "header.php").write_text(
            '<!DOCTYPE html>\n<html <?php language_attributes(); ?>>\n<head>\n'
            '  <meta charset="<?php bloginfo(\'charset\'); ?>">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            "  <?php wp_head(); ?>\n</head>\n"
            "<body <?php body_class(); ?>>\n"
            f'<header class="container">\n  <h1><a href="<?php echo home_url(); ?>">{name}</a></h1>\n'
            "  <nav><?php wp_nav_menu(['theme_location' => 'primary']); ?></nav>\n</header>\n",
            encoding="utf-8",
        )
        (base / "footer.php").write_text(
            '<footer class="container">\n'
            f"  <p>&copy; <?php echo date('Y'); ?> {name}</p>\n"
            "</footer>\n<?php wp_footer(); ?>\n</body>\n</html>\n",
            encoding="utf-8",
        )
        (base / "functions.php").write_text(
            "<?php\n\n"
            f"function {slug.replace('-', '_')}_setup() {{\n"
            "    add_theme_support('title-tag');\n"
            "    add_theme_support('post-thumbnails');\n"
            "    register_nav_menus(['primary' => 'Primary Menu']);\n}\n"
            f"add_action('after_setup_theme', '{slug.replace('-', '_')}_setup');\n\n"
            f"function {slug.replace('-', '_')}_styles() {{\n"
            f"    wp_enqueue_style('{slug}-style', get_stylesheet_uri());\n}}\n"
            f"add_action('wp_enqueue_scripts', '{slug.replace('-', '_')}_styles');\n",
            encoding="utf-8",
        )
        (base / "screenshot.png").write_bytes(b"")  # placeholder
        (base / "README.md").write_text(
            f"# {name}\n\nWordPress theme.\n\n"
            "Copy this folder to `wp-content/themes/` and activate from WP Admin.\n",
            encoding="utf-8",
        )
        return f"Created WordPress theme at {base}"

    def _scaffold_chrome_extension(self, base: Path, name: str) -> str:
        import json
        base.mkdir(parents=True)

        manifest = {
            "manifest_version": 3,
            "name": name,
            "version": "1.0.0",
            "description": f"{name} Chrome extension",
            "permissions": ["storage", "activeTab"],
            "action": {
                "default_popup": "popup.html",
                "default_icon": "icon.png",
            },
            "background": {
                "service_worker": "background.js",
            },
        }
        (base / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (base / "popup.html").write_text(
            '<!DOCTYPE html>\n<html>\n<head>\n'
            '  <meta charset="UTF-8">\n  <style>\n'
            "    body { width: 300px; padding: 16px; font-family: system-ui; }\n"
            "    h2 { margin: 0 0 8px; }\n  </style>\n</head>\n<body>\n"
            f'  <h2>{name}</h2>\n  <p id="status">Ready</p>\n'
            '  <button id="btn">Click me</button>\n'
            '  <script src="popup.js"></script>\n</body>\n</html>\n',
            encoding="utf-8",
        )
        (base / "popup.js").write_text(
            'document.getElementById("btn").addEventListener("click", () => {\n'
            '  document.getElementById("status").textContent = "Clicked!";\n'
            "});\n",
            encoding="utf-8",
        )
        (base / "background.js").write_text(
            "chrome.runtime.onInstalled.addListener(() => {\n"
            f'  console.log("{name} installed");\n'
            "});\n",
            encoding="utf-8",
        )
        (base / "README.md").write_text(
            f"# {name}\n\nChrome Extension (Manifest V3).\n\n"
            "1. Open `chrome://extensions/`\n"
            "2. Enable Developer mode\n"
            "3. Click 'Load unpacked' and select this folder\n",
            encoding="utf-8",
        )
        return f"Created Chrome Extension (Manifest V3) at {base}"

    # ── Helpers ───────────────────────────────────────

    async def _execute_command(
        self, cmd: str, cwd: str | None = None, timeout: int = 60
    ) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or str(HOME_DIR),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Command timed out after {timeout}s: {cmd}"

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += "\n[STDERR]\n" + stderr.decode("utf-8", errors="replace")

        if len(output) > 10000:
            output = output[:10000] + "\n... [truncated]"

        return f"$ {cmd}\nExit code: {proc.returncode}\n\n{output.strip()}"

    @staticmethod
    def _shell_quote(s: str) -> str:
        import shlex
        return shlex.quote(s)
