"""Website builder tool — create, preview, deploy, and edit websites.

Generates complete websites from templates, starts local preview
servers, deploys to hosting, and edits existing sites.
"""

import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)

HOME_DIR = Path.home()


# HTML templates for different website types
TEMPLATES = {
    "landing": {
        "description": "Landing page with hero, features, and CTA",
        "files": {
            "index.html": """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{description}">
    <title>{name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, -apple-system, sans-serif; color: #333; }}
        .hero {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; padding: 80px 20px; text-align: center; }}
        .hero h1 {{ font-size: 3rem; margin-bottom: 16px; }}
        .hero p {{ font-size: 1.2rem; opacity: 0.9; max-width: 600px; margin: 0 auto 32px; }}
        .btn {{ display: inline-block; padding: 14px 32px; background: white;
                color: #667eea; border-radius: 8px; text-decoration: none;
                font-weight: 600; font-size: 1.1rem; }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
        .features {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                     gap: 32px; padding: 60px 20px; max-width: 1000px; margin: 0 auto; }}
        .feature {{ text-align: center; padding: 24px; }}
        .feature h3 {{ margin: 12px 0 8px; }}
        .feature p {{ color: #666; }}
        .feature .icon {{ font-size: 2.5rem; }}
        footer {{ text-align: center; padding: 32px; color: #999; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <section class="hero">
        <h1>{name}</h1>
        <p>{description}</p>
        <a href="#features" class="btn">Get Started</a>
    </section>
    <section class="features" id="features">
        <div class="feature">
            <div class="icon">&#9889;</div>
            <h3>Fast</h3>
            <p>Lightning fast performance out of the box.</p>
        </div>
        <div class="feature">
            <div class="icon">&#128274;</div>
            <h3>Secure</h3>
            <p>Built with security best practices.</p>
        </div>
        <div class="feature">
            <div class="icon">&#128640;</div>
            <h3>Easy</h3>
            <p>Get up and running in minutes.</p>
        </div>
    </section>
    <footer>&copy; 2025 {name}. All rights reserved.</footer>
</body>
</html>""",
        },
    },
    "portfolio": {
        "description": "Portfolio with projects grid and about section",
        "files": {
            "index.html": """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - Portfolio</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: #0a0a0a; color: #fff; }}
        header {{ padding: 60px 20px; text-align: center; }}
        header h1 {{ font-size: 2.5rem; }}
        header p {{ color: #888; margin-top: 8px; }}
        .projects {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                     gap: 24px; padding: 40px 20px; max-width: 1100px; margin: 0 auto; }}
        .card {{ background: #1a1a1a; border-radius: 12px; padding: 24px;
                 border: 1px solid #333; transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-4px); border-color: #667eea; }}
        .card h3 {{ margin-bottom: 8px; }}
        .card p {{ color: #aaa; font-size: 0.95rem; }}
        .card .tag {{ display: inline-block; background: #333; padding: 4px 10px;
                      border-radius: 4px; font-size: 0.8rem; margin-top: 12px; margin-right: 4px; }}
        .about {{ max-width: 700px; margin: 60px auto; padding: 40px 20px; text-align: center; }}
        .about p {{ color: #aaa; line-height: 1.7; }}
        footer {{ text-align: center; padding: 32px; color: #555; }}
    </style>
</head>
<body>
    <header>
        <h1>{name}</h1>
        <p>{description}</p>
    </header>
    <section class="projects">
        <div class="card">
            <h3>Project One</h3>
            <p>A brief description of this amazing project.</p>
            <span class="tag">Python</span><span class="tag">FastAPI</span>
        </div>
        <div class="card">
            <h3>Project Two</h3>
            <p>Another cool project with interesting features.</p>
            <span class="tag">React</span><span class="tag">Node.js</span>
        </div>
        <div class="card">
            <h3>Project Three</h3>
            <p>Something creative and well-designed.</p>
            <span class="tag">HTML</span><span class="tag">CSS</span>
        </div>
    </section>
    <section class="about">
        <h2>About</h2>
        <p>Welcome to my portfolio. I build things for the web.</p>
    </section>
    <footer>&copy; 2025 {name}</footer>
</body>
</html>""",
        },
    },
    "dashboard": {
        "description": "Admin dashboard with sidebar and cards",
        "files": {
            "index.html": """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; display: flex; min-height: 100vh; background: #f0f2f5; }}
        .sidebar {{ width: 240px; background: #1a1a2e; color: white; padding: 20px; flex-shrink: 0; }}
        .sidebar h2 {{ margin-bottom: 24px; font-size: 1.2rem; }}
        .sidebar a {{ display: block; color: #aaa; text-decoration: none; padding: 10px 12px;
                      border-radius: 6px; margin-bottom: 4px; }}
        .sidebar a:hover, .sidebar a.active {{ background: #16213e; color: white; }}
        .main {{ flex: 1; padding: 24px; }}
        .main h1 {{ margin-bottom: 24px; color: #1a1a2e; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
        .stat-card {{ background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-card .label {{ color: #888; font-size: 0.9rem; }}
        .stat-card .value {{ font-size: 2rem; font-weight: 700; margin-top: 8px; }}
    </style>
</head>
<body>
    <nav class="sidebar">
        <h2>{name}</h2>
        <a href="#" class="active">Dashboard</a>
        <a href="#">Users</a>
        <a href="#">Analytics</a>
        <a href="#">Settings</a>
    </nav>
    <main class="main">
        <h1>Dashboard</h1>
        <div class="cards">
            <div class="stat-card"><div class="label">Total Users</div><div class="value">1,234</div></div>
            <div class="stat-card"><div class="label">Revenue</div><div class="value">$5,678</div></div>
            <div class="stat-card"><div class="label">Orders</div><div class="value">89</div></div>
            <div class="stat-card"><div class="label">Growth</div><div class="value">+12%</div></div>
        </div>
    </main>
</body>
</html>""",
        },
    },
}


class WebsiteBuilderTool(BaseTool):
    """Generate complete websites from templates."""

    name = "website_builder"
    description = (
        "Create complete websites from templates (landing page, portfolio, dashboard), "
        "start local preview servers, and edit existing site files. "
        "All sites are mobile responsive with clean HTML/CSS."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create_website",
                    "preview_website",
                    "edit_file",
                    "list_templates",
                    "deploy_website",
                    "add_page",
                    "optimize_website",
                ],
                "description": "The action to perform",
            },
            "template": {
                "type": "string",
                "description": "Template name: landing, portfolio, dashboard (for create_website)",
            },
            "project_path": {
                "type": "string",
                "description": "Path for the website project",
            },
            "name": {
                "type": "string",
                "description": "Website/project name",
            },
            "description": {
                "type": "string",
                "description": "Website description",
            },
            "file_path": {
                "type": "string",
                "description": "File to edit (for edit_file)",
            },
            "content": {
                "type": "string",
                "description": "New file content (for edit_file)",
            },
            "port": {
                "type": "integer",
                "description": "Port for preview server (default 8000)",
            },
            "platform": {
                "type": "string",
                "enum": ["netlify", "github-pages"],
                "description": "Deployment platform (for deploy_website)",
            },
            "page_name": {
                "type": "string",
                "description": "Page name e.g. 'about', 'contact' (for add_page)",
            },
            "page_title": {
                "type": "string",
                "description": "Page title (for add_page)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._preview_processes: dict[str, asyncio.subprocess.Process] = {}

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "create_website":
                return self._create_website(
                    kwargs.get("template", "landing"),
                    kwargs.get("project_path", ""),
                    kwargs.get("name", "My Website"),
                    kwargs.get("description", "A beautiful website"),
                )
            elif action == "preview_website":
                return await self._preview(
                    kwargs.get("project_path", ""),
                    kwargs.get("port", 8000),
                )
            elif action == "edit_file":
                return self._edit_file(
                    kwargs.get("file_path", ""),
                    kwargs.get("content", ""),
                )
            elif action == "list_templates":
                return self._list_templates()
            elif action == "deploy_website":
                return await self._deploy(
                    kwargs.get("project_path", ""),
                    kwargs.get("platform", "netlify"),
                )
            elif action == "add_page":
                return self._add_page(
                    kwargs.get("project_path", ""),
                    kwargs.get("page_name", ""),
                    kwargs.get("page_title", ""),
                    kwargs.get("content", ""),
                    kwargs.get("name", "My Website"),
                )
            elif action == "optimize_website":
                return self._optimize(kwargs.get("project_path", ""))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Website builder error: %s", action)
            return f"Error: {e}"

    def _create_website(
        self, template: str, project_path: str, name: str, description: str
    ) -> str:
        if not project_path:
            return "Error: project_path is required."

        tpl = TEMPLATES.get(template)
        if not tpl:
            available = ", ".join(TEMPLATES.keys())
            return f"Unknown template '{template}'. Available: {available}"

        base = Path(project_path).expanduser()
        if base.exists():
            return f"Directory already exists: {base}"

        base.mkdir(parents=True)

        for filename, content in tpl["files"].items():
            rendered = content.format(name=name, description=description)
            (base / filename).write_text(rendered, encoding="utf-8")

        files = list(tpl["files"].keys())
        return (
            f"Created '{template}' website at {base}\n"
            f"Files: {', '.join(files)}\n\n"
            f"Preview with: action=preview_website, project_path={base}"
        )

    async def _preview(self, project_path: str, port: int) -> str:
        if not project_path:
            return "Error: project_path is required."

        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            return f"Directory not found: {path}"

        # Stop existing preview on same port
        key = str(port)
        if key in self._preview_processes:
            self._preview_processes[key].kill()

        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "http.server", str(port),
            cwd=str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._preview_processes[key] = proc

        return f"Preview server started at http://localhost:{port}\nServing: {path}"

    def _edit_file(self, file_path: str, content: str) -> str:
        if not file_path:
            return "Error: file_path is required."
        if not content:
            return "Error: content is required."

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"File not found: {path}"

        path.write_text(content, encoding="utf-8")
        return f"Updated {path} ({len(content)} chars)"

    def _list_templates(self) -> str:
        lines = ["Available website templates:\n"]
        for name, tpl in TEMPLATES.items():
            lines.append(f"  - {name}: {tpl['description']}")
        return "\n".join(lines)

    async def _deploy(self, project_path: str, platform: str) -> str:
        """Deploy website using Netlify CLI or GitHub Pages."""
        if not project_path:
            return "Error: project_path is required."

        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            return f"Directory not found: {path}"

        platform = platform.lower()

        if platform == "netlify":
            # Check if netlify-cli is available
            try:
                proc = await asyncio.create_subprocess_exec(
                    "npx", "netlify-cli", "deploy", "--prod", "--dir", str(path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                output = stdout.decode("utf-8", errors="replace")
                if proc.returncode == 0:
                    # Extract URL from output
                    url_match = re.search(r'(https://[^\s]+\.netlify\.app)', output)
                    url = url_match.group(1) if url_match else "see output"
                    return f"Deployed to Netlify!\nURL: {url}\n\n{output[-500:]}"
                else:
                    err = stderr.decode("utf-8", errors="replace")
                    return (
                        f"Netlify deploy failed (exit {proc.returncode}).\n{err[:500]}\n\n"
                        "Make sure you've run 'npx netlify-cli login' first."
                    )
            except FileNotFoundError:
                return (
                    "Error: netlify-cli not found.\n"
                    "Install with: npm install -g netlify-cli\n"
                    "Then: netlify login"
                )
            except asyncio.TimeoutError:
                return "Deployment timed out (2 min limit)."

        elif platform == "github-pages":
            # Initialize git, commit, and push to gh-pages branch
            git_dir = path / ".git"
            cmds = []
            if not git_dir.exists():
                cmds.append(("git", "init"))
                cmds.append(("git", "checkout", "-b", "gh-pages"))
            else:
                cmds.append(("git", "checkout", "-B", "gh-pages"))

            cmds.append(("git", "add", "."))
            cmds.append(("git", "commit", "-m", "Deploy to GitHub Pages"))

            results = []
            for cmd in cmds:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, cwd=str(path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                results.append(stdout.decode(errors="replace").strip())

            return (
                f"Prepared for GitHub Pages deployment at {path}\n"
                "Branch: gh-pages\n\n"
                "Next steps:\n"
                "1. git remote add origin <your-repo-url>\n"
                "2. git push -u origin gh-pages\n"
                "3. Enable GitHub Pages in repo Settings -> Pages -> Branch: gh-pages"
            )
        else:
            return f"Unknown platform '{platform}'. Supported: netlify, github-pages"

    def _add_page(self, project_path: str, page_name: str, page_title: str,
                  content: str, site_name: str) -> str:
        """Add a new page to an existing website."""
        if not project_path:
            return "Error: project_path is required."
        if not page_name:
            return "Error: page_name is required (e.g. 'about', 'contact')."

        path = Path(project_path).expanduser()
        if not path.exists():
            return f"Directory not found: {path}"

        slug = page_name.lower().replace(" ", "-")
        title = page_title or page_name.title()
        body_content = content or f"<h1>{title}</h1>\n<p>Content coming soon.</p>"

        # Read index.html to extract existing styles
        index_file = path / "index.html"
        style_block = ""
        if index_file.exists():
            index_html = index_file.read_text(encoding="utf-8")
            style_match = re.search(r'<style>(.*?)</style>', index_html, re.DOTALL)
            if style_match:
                style_block = style_match.group(0)

        if not style_block:
            style_block = '<style>body { font-family: system-ui, sans-serif; padding: 2rem; }</style>'

        page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {site_name}</title>
    {style_block}
</head>
<body>
    <nav><a href="index.html">Home</a> | <a href="{slug}.html">{title}</a></nav>
    <main style="max-width: 800px; margin: 40px auto; padding: 0 20px;">
        {body_content}
    </main>
</body>
</html>"""

        page_file = path / f"{slug}.html"
        page_file.write_text(page_html, encoding="utf-8")

        # Add nav link to index.html if it exists
        nav_added = False
        if index_file.exists():
            index_content = index_file.read_text(encoding="utf-8")
            if f"{slug}.html" not in index_content:
                # Try to add a nav link before </body>
                nav_link = f'    <nav style="padding:12px 20px;background:#f5f5f5;"><a href="index.html">Home</a> | <a href="{slug}.html">{title}</a></nav>\n'
                if "<nav" not in index_content and "<body>" in index_content:
                    index_content = index_content.replace("<body>", f"<body>\n{nav_link}", 1)
                    index_file.write_text(index_content, encoding="utf-8")
                    nav_added = True

        result = f"Created page: {page_file}"
        if nav_added:
            result += "\nAdded navigation link to index.html"
        return result

    def _optimize(self, project_path: str) -> str:
        """Optimize website: minify HTML/CSS, report file sizes."""
        if not project_path:
            return "Error: project_path is required."

        path = Path(project_path).expanduser()
        if not path.exists():
            return f"Directory not found: {path}"

        results = []
        total_saved = 0

        for ext in ("*.html", "*.css", "*.js"):
            for f in path.rglob(ext):
                original = f.read_text(encoding="utf-8")
                original_size = len(original.encode("utf-8"))

                if f.suffix == ".css":
                    # Basic CSS minification
                    minified = re.sub(r'/\*.*?\*/', '', original, flags=re.DOTALL)
                    minified = re.sub(r'\s+', ' ', minified)
                    minified = re.sub(r'\s*([{}:;,>~+])\s*', r'\1', minified)
                    minified = minified.strip()
                elif f.suffix == ".html":
                    # Basic HTML minification — remove excess whitespace between tags
                    minified = re.sub(r'>\s+<', '><', original)
                    minified = re.sub(r'\s{2,}', ' ', minified)
                elif f.suffix == ".js":
                    # Basic JS: remove single-line comments, collapse whitespace
                    minified = re.sub(r'//.*$', '', original, flags=re.MULTILINE)
                    minified = re.sub(r'\s{2,}', ' ', minified)
                else:
                    continue

                new_size = len(minified.encode("utf-8"))
                saved = original_size - new_size

                if saved > 0:
                    f.write_text(minified, encoding="utf-8")
                    total_saved += saved
                    pct = (saved / original_size) * 100
                    results.append(f"  {f.name}: {original_size}B -> {new_size}B ({pct:.0f}% smaller)")
                else:
                    results.append(f"  {f.name}: {original_size}B (already optimized)")

        if not results:
            return "No HTML, CSS, or JS files found to optimize."

        return (
            f"Optimized {len(results)} files in {path}:\n"
            + "\n".join(results)
            + f"\n\nTotal saved: {total_saved} bytes"
        )
