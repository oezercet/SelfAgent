"""Website builder templates -- restaurant, saas-landing.

Third set of HTML templates used by WebsiteBuilderTool.
See also: website_templates.py, website_templates_extra.py.
"""

TEMPLATES_MORE = {
    "restaurant": {
        "description": "Restaurant site with menu, location, and hours",
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
        body {{ font-family: Georgia, serif; color: #333; }}
        .hero {{ background: linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)),
                 linear-gradient(135deg, #8B4513, #D2691E); color: white;
                 text-align: center; padding: 100px 20px; }}
        .hero h1 {{ font-size: 3rem; font-family: Georgia, serif; letter-spacing: 2px; }}
        .hero p {{ font-size: 1.2rem; opacity: 0.9; margin: 12px 0 24px; }}
        .hero .btn {{ display: inline-block; padding: 14px 32px; border: 2px solid white;
                      color: white; text-decoration: none; font-size: 1rem; letter-spacing: 1px; }}
        .hero .btn:hover {{ background: white; color: #333; }}
        nav {{ background: #2c1810; text-align: center; padding: 14px; position: sticky; top: 0; z-index: 10; }}
        nav a {{ color: #ddd; text-decoration: none; margin: 0 20px; font-size: 0.95rem; text-transform: uppercase;
                 letter-spacing: 1px; }}
        nav a:hover {{ color: #D2691E; }}
        section {{ max-width: 900px; margin: 0 auto; padding: 60px 20px; }}
        section h2 {{ text-align: center; font-size: 2rem; margin-bottom: 32px; color: #2c1810; }}
        .menu-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .menu-item {{ display: flex; justify-content: space-between; padding: 12px 0;
                      border-bottom: 1px dotted #ccc; }}
        .menu-item .name {{ font-weight: bold; }}
        .menu-item .desc {{ color: #888; font-size: 0.85rem; }}
        .menu-item .price {{ color: #8B4513; font-weight: bold; white-space: nowrap; margin-left: 16px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; text-align: center; }}
        .info-card {{ padding: 24px; }}
        .info-card h3 {{ color: #2c1810; margin-bottom: 8px; }}
        .info-card p {{ color: #666; line-height: 1.6; }}
        footer {{ background: #2c1810; color: #aaa; text-align: center; padding: 32px; }}
        @media (max-width: 768px) {{ .menu-grid, .info-grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <nav><a href="#menu">Menu</a><a href="#about">About</a><a href="#contact">Contact</a></nav>
    <section class="hero">
        <h1>{name}</h1>
        <p>{description}</p>
        <a href="#menu" class="btn">View Menu</a>
    </section>
    <section id="menu">
        <h2>Our Menu</h2>
        <div class="menu-grid">
            <div>
                <h3 style="margin-bottom:12px;color:#2c1810;">Starters</h3>
                <div class="menu-item"><div><div class="name">Bruschetta</div><div class="desc">Toasted bread with tomatoes</div></div><div class="price">$9</div></div>
                <div class="menu-item"><div><div class="name">Soup of the Day</div><div class="desc">Chef's daily creation</div></div><div class="price">$7</div></div>
                <div class="menu-item"><div><div class="name">Caesar Salad</div><div class="desc">Romaine, croutons, parmesan</div></div><div class="price">$11</div></div>
            </div>
            <div>
                <h3 style="margin-bottom:12px;color:#2c1810;">Main Courses</h3>
                <div class="menu-item"><div><div class="name">Grilled Salmon</div><div class="desc">With seasonal vegetables</div></div><div class="price">$24</div></div>
                <div class="menu-item"><div><div class="name">Ribeye Steak</div><div class="desc">12oz, with fries</div></div><div class="price">$32</div></div>
                <div class="menu-item"><div><div class="name">Pasta Primavera</div><div class="desc">Fresh garden vegetables</div></div><div class="price">$18</div></div>
            </div>
        </div>
    </section>
    <section id="about" style="background:#f9f6f2;">
        <h2>Visit Us</h2>
        <div class="info-grid">
            <div class="info-card"><h3>&#128205; Location</h3><p>123 Main Street<br>New York, NY 10001</p></div>
            <div class="info-card"><h3>&#128337; Hours</h3><p>Mon-Fri: 11am - 10pm<br>Sat-Sun: 10am - 11pm</p></div>
            <div class="info-card"><h3>&#128222; Contact</h3><p>(555) 123-4567<br>info@{name}.com</p></div>
        </div>
    </section>
    <footer>&copy; 2025 {name}. All rights reserved.</footer>
</body>
</html>""",
        },
    },
    "saas-landing": {
        "description": "SaaS landing page with pricing and feature comparison",
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
        body {{ font-family: system-ui, sans-serif; color: #333; }}
        nav {{ display: flex; justify-content: space-between; align-items: center; padding: 16px 32px;
               background: white; border-bottom: 1px solid #eee; position: sticky; top: 0; z-index: 10; }}
        nav .logo {{ font-size: 1.3rem; font-weight: 700; color: #667eea; }}
        nav a {{ color: #555; text-decoration: none; margin-left: 24px; }}
        nav .cta {{ background: #667eea; color: white; padding: 8px 20px; border-radius: 6px; }}
        .hero {{ text-align: center; padding: 80px 20px 60px; }}
        .hero h1 {{ font-size: 3rem; max-width: 700px; margin: 0 auto 16px; line-height: 1.2; }}
        .hero p {{ color: #666; font-size: 1.2rem; max-width: 500px; margin: 0 auto 32px; }}
        .hero .btn {{ display: inline-block; padding: 14px 36px; background: #667eea; color: white;
                      border-radius: 8px; text-decoration: none; font-size: 1.1rem; font-weight: 600; }}
        .hero .btn:hover {{ background: #5a6fd6; }}
        .features {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 32px;
                     max-width: 1000px; margin: 0 auto; padding: 60px 20px; }}
        .feature {{ text-align: center; padding: 24px; }}
        .feature .icon {{ font-size: 2.5rem; margin-bottom: 12px; }}
        .feature h3 {{ margin-bottom: 8px; }}
        .feature p {{ color: #666; font-size: 0.95rem; }}
        .pricing {{ background: #f8f9ff; padding: 60px 20px; text-align: center; }}
        .pricing h2 {{ font-size: 2rem; margin-bottom: 40px; }}
        .plans {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
                  max-width: 900px; margin: 0 auto; }}
        .plan {{ background: white; border-radius: 12px; padding: 32px 24px;
                 box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .plan.featured {{ border: 2px solid #667eea; transform: scale(1.05); }}
        .plan h3 {{ font-size: 1.1rem; color: #667eea; margin-bottom: 8px; }}
        .plan .price {{ font-size: 2.5rem; font-weight: 700; margin: 12px 0; }}
        .plan .price span {{ font-size: 1rem; color: #999; font-weight: 400; }}
        .plan ul {{ list-style: none; text-align: left; margin: 20px 0; }}
        .plan li {{ padding: 8px 0; color: #555; border-bottom: 1px solid #f0f0f0; }}
        .plan li::before {{ content: "\\2713 "; color: #667eea; font-weight: bold; }}
        .plan .btn {{ display: block; padding: 12px; background: #667eea; color: white;
                      border-radius: 6px; text-decoration: none; text-align: center; margin-top: 20px; }}
        footer {{ text-align: center; padding: 32px; color: #999; border-top: 1px solid #eee; }}
        @media (max-width: 768px) {{ .features, .plans {{ grid-template-columns: 1fr; }}
            .plan.featured {{ transform: none; }} }}
    </style>
</head>
<body>
    <nav>
        <div class="logo">{name}</div>
        <div><a href="#features">Features</a><a href="#pricing">Pricing</a><a href="#" class="cta">Get Started</a></div>
    </nav>
    <section class="hero">
        <h1>{name} — {description}</h1>
        <p>The all-in-one platform to grow your business. Start free, scale as you grow.</p>
        <a href="#" class="btn">Start Free Trial</a>
    </section>
    <section class="features" id="features">
        <div class="feature"><div class="icon">&#9889;</div><h3>Lightning Fast</h3><p>Optimized for speed with global CDN and edge caching.</p></div>
        <div class="feature"><div class="icon">&#128274;</div><h3>Enterprise Security</h3><p>SOC 2 compliant with end-to-end encryption.</p></div>
        <div class="feature"><div class="icon">&#128200;</div><h3>Advanced Analytics</h3><p>Real-time dashboards and custom reports.</p></div>
        <div class="feature"><div class="icon">&#128257;</div><h3>Integrations</h3><p>Connect with 200+ tools and services.</p></div>
        <div class="feature"><div class="icon">&#129302;</div><h3>AI-Powered</h3><p>Smart automation that learns from your data.</p></div>
        <div class="feature"><div class="icon">&#128101;</div><h3>Team Collaboration</h3><p>Work together with real-time editing and comments.</p></div>
    </section>
    <section class="pricing" id="pricing">
        <h2>Simple, Transparent Pricing</h2>
        <div class="plans">
            <div class="plan">
                <h3>Starter</h3>
                <div class="price">$9<span>/month</span></div>
                <ul><li>5 projects</li><li>10GB storage</li><li>Email support</li><li>Basic analytics</li></ul>
                <a href="#" class="btn">Get Started</a>
            </div>
            <div class="plan featured">
                <h3>Professional</h3>
                <div class="price">$29<span>/month</span></div>
                <ul><li>Unlimited projects</li><li>100GB storage</li><li>Priority support</li><li>Advanced analytics</li><li>API access</li></ul>
                <a href="#" class="btn">Start Free Trial</a>
            </div>
            <div class="plan">
                <h3>Enterprise</h3>
                <div class="price">$99<span>/month</span></div>
                <ul><li>Everything in Pro</li><li>Unlimited storage</li><li>Dedicated support</li><li>Custom integrations</li><li>SLA guarantee</li></ul>
                <a href="#" class="btn">Contact Sales</a>
            </div>
        </div>
    </section>
    <footer>&copy; 2025 {name}. All rights reserved.</footer>
</body>
</html>""",
        },
    },
}
