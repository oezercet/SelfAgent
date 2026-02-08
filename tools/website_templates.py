"""Website builder templates -- landing, portfolio, dashboard, blog.

These are the first set of HTML templates used by WebsiteBuilderTool.
The second set lives in website_templates_extra.py.
"""

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
    "blog": {
        "description": "Blog with posts, sidebar, and dark theme",
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
        body {{ font-family: Georgia, serif; background: #fafafa; color: #333; }}
        header {{ background: #1a1a2e; color: white; padding: 40px 20px; text-align: center; }}
        header h1 {{ font-size: 2.2rem; }}
        header p {{ color: #aaa; margin-top: 6px; }}
        nav {{ background: #16213e; padding: 12px 20px; text-align: center; }}
        nav a {{ color: #ddd; text-decoration: none; margin: 0 16px; font-size: 0.95rem; }}
        nav a:hover {{ color: white; }}
        .container {{ max-width: 900px; margin: 40px auto; padding: 0 20px; display: grid;
                      grid-template-columns: 1fr 280px; gap: 32px; }}
        .posts article {{ background: white; padding: 28px; margin-bottom: 24px;
                          border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .posts h2 {{ margin-bottom: 8px; }}
        .posts .meta {{ color: #888; font-size: 0.85rem; margin-bottom: 12px; }}
        .posts p {{ line-height: 1.7; color: #555; }}
        .posts .read-more {{ display: inline-block; margin-top: 12px; color: #667eea; }}
        .sidebar .widget {{ background: white; padding: 20px; border-radius: 8px;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }}
        .sidebar h3 {{ margin-bottom: 12px; font-size: 1rem; }}
        .sidebar ul {{ list-style: none; }}
        .sidebar li {{ padding: 4px 0; }}
        .sidebar a {{ color: #667eea; text-decoration: none; }}
        footer {{ text-align: center; padding: 32px; color: #999; border-top: 1px solid #eee; margin-top: 40px; }}
        @media (max-width: 768px) {{ .container {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <header><h1>{name}</h1><p>{description}</p></header>
    <nav><a href="#">Home</a><a href="#">Archive</a><a href="#">About</a></nav>
    <div class="container">
        <section class="posts">
            <article>
                <h2>Getting Started with SelfAgent</h2>
                <div class="meta">January 15, 2025 &bull; 5 min read</div>
                <p>Welcome to the first post on this blog. Here we explore how to set up your own AI assistant...</p>
                <a href="#" class="read-more">Read more &rarr;</a>
            </article>
            <article>
                <h2>Building a Modern Web Experience</h2>
                <div class="meta">January 10, 2025 &bull; 3 min read</div>
                <p>In this post, we discuss best practices for creating responsive, accessible websites...</p>
                <a href="#" class="read-more">Read more &rarr;</a>
            </article>
        </section>
        <aside class="sidebar">
            <div class="widget"><h3>About</h3><p>A blog about technology and development.</p></div>
            <div class="widget"><h3>Categories</h3><ul><li><a href="#">Technology</a></li><li><a href="#">Design</a></li><li><a href="#">Tutorials</a></li></ul></div>
        </aside>
    </div>
    <footer>&copy; 2025 {name}</footer>
</body>
</html>""",
        },
    },
}
