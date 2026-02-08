"""Project scaffold templates for CodeWriterTool.

Each function creates a project directory structure and returns
a human-readable summary string.
"""

from pathlib import Path


def scaffold_python_script(base: Path, name: str) -> str:
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


def scaffold_python_api(base: Path, name: str) -> str:
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


def scaffold_html_site(base: Path, name: str) -> str:
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


def scaffold_node_api(base: Path, name: str) -> str:
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


def scaffold_react_app(base: Path, name: str) -> str:
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


def scaffold_wordpress_theme(base: Path, name: str) -> str:
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


def scaffold_chrome_extension(base: Path, name: str) -> str:
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


# Registry mapping project_type strings to scaffold functions.
SCAFFOLD_REGISTRY = {
    "python-script": scaffold_python_script,
    "python-api": scaffold_python_api,
    "html-site": scaffold_html_site,
    "node-api": scaffold_node_api,
    "react-app": scaffold_react_app,
    "wordpress-theme": scaffold_wordpress_theme,
    "chrome-extension": scaffold_chrome_extension,
}
