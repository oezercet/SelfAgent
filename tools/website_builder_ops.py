"""Website builder operations -- deploy, add_page, optimize.

Helper functions extracted from WebsiteBuilderTool to keep file sizes
manageable. These are called as methods via the main class.
"""

import asyncio
import re
from pathlib import Path


async def deploy_website(project_path: str, platform: str) -> str:
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


def add_page(project_path: str, page_name: str, page_title: str,
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


def optimize_website(project_path: str) -> str:
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
                # Basic HTML minification -- remove excess whitespace between tags
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
