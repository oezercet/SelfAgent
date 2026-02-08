"""Website builder templates -- e-commerce, documentation.

Second set of HTML templates used by WebsiteBuilderTool.
See also: website_templates.py, website_templates_more.py.
"""

TEMPLATES_EXTRA = {
    "e-commerce": {
        "description": "E-commerce product listing with cart UI",
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
        body {{ font-family: system-ui, sans-serif; background: #f5f5f5; color: #333; }}
        header {{ background: white; padding: 16px 24px; display: flex; justify-content: space-between;
                  align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 10; }}
        header h1 {{ font-size: 1.4rem; }}
        .cart-btn {{ background: #667eea; color: white; border: none; padding: 8px 20px;
                     border-radius: 6px; cursor: pointer; font-size: 0.95rem; }}
        .cart-btn:hover {{ background: #5a6fd6; }}
        .products {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
                     gap: 24px; padding: 32px 24px; max-width: 1200px; margin: 0 auto; }}
        .product {{ background: white; border-radius: 12px; overflow: hidden;
                    box-shadow: 0 1px 4px rgba(0,0,0,0.08); transition: transform 0.2s; }}
        .product:hover {{ transform: translateY(-4px); }}
        .product .img {{ height: 200px; background: linear-gradient(135deg, #667eea22, #764ba222);
                         display: flex; align-items: center; justify-content: center; font-size: 3rem; }}
        .product .info {{ padding: 16px; }}
        .product h3 {{ margin-bottom: 4px; }}
        .product .price {{ font-size: 1.3rem; font-weight: 700; color: #667eea; margin: 8px 0; }}
        .product .old-price {{ text-decoration: line-through; color: #999; font-size: 0.9rem; margin-left: 8px; }}
        .add-btn {{ width: 100%; padding: 10px; background: #333; color: white; border: none;
                    border-radius: 6px; cursor: pointer; font-size: 0.95rem; }}
        .add-btn:hover {{ background: #555; }}
        footer {{ text-align: center; padding: 32px; color: #999; }}
    </style>
</head>
<body>
    <header>
        <h1>{name}</h1>
        <button class="cart-btn" id="cartBtn">Cart (0)</button>
    </header>
    <section class="products" id="products"></section>
    <footer>&copy; 2025 {name}. All rights reserved.</footer>
    <script>
        var products = [
            {{ name: "Wireless Headphones", price: 79.99, old: 99.99, icon: "&#127911;" }},
            {{ name: "Smart Watch", price: 199.99, old: 249.99, icon: "&#9201;" }},
            {{ name: "Laptop Stand", price: 49.99, old: null, icon: "&#128187;" }},
            {{ name: "USB-C Hub", price: 39.99, old: 59.99, icon: "&#128268;" }},
            {{ name: "Mechanical Keyboard", price: 129.99, old: null, icon: "&#9000;" }},
            {{ name: "Webcam HD", price: 69.99, old: 89.99, icon: "&#128247;" }},
        ];
        var cart = 0;
        var container = document.getElementById("products");
        products.forEach(function(p) {{
            var old = p.old ? '<span class="old-price">$' + p.old + '</span>' : '';
            container.innerHTML += '<div class="product"><div class="img">' + p.icon + '</div>'
                + '<div class="info"><h3>' + p.name + '</h3><div class="price">$' + p.price + old + '</div>'
                + '<button class="add-btn" onclick="addToCart()">Add to Cart</button></div></div>';
        }});
        function addToCart() {{
            cart++;
            document.getElementById("cartBtn").textContent = "Cart (" + cart + ")";
        }}
    </script>
</body>
</html>""",
        },
    },
    "documentation": {
        "description": "Documentation site with sidebar navigation",
        "files": {
            "index.html": """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} — Docs</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; display: flex; min-height: 100vh; }}
        .sidebar {{ width: 260px; background: #1a1a2e; color: white; padding: 24px 16px;
                    flex-shrink: 0; position: sticky; top: 0; height: 100vh; overflow-y: auto; }}
        .sidebar h2 {{ font-size: 1.1rem; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #333; }}
        .sidebar .section {{ margin-bottom: 16px; }}
        .sidebar .section-title {{ color: #888; font-size: 0.75rem; text-transform: uppercase;
                                   letter-spacing: 1px; margin-bottom: 6px; }}
        .sidebar a {{ display: block; color: #ccc; text-decoration: none; padding: 6px 12px;
                      border-radius: 4px; font-size: 0.9rem; margin-bottom: 2px; }}
        .sidebar a:hover, .sidebar a.active {{ background: #16213e; color: white; }}
        .content {{ flex: 1; padding: 48px 40px; max-width: 800px; }}
        .content h1 {{ font-size: 2rem; margin-bottom: 8px; color: #1a1a2e; }}
        .content .subtitle {{ color: #888; margin-bottom: 32px; }}
        .content h2 {{ margin-top: 32px; margin-bottom: 12px; color: #333; padding-bottom: 6px;
                       border-bottom: 1px solid #eee; }}
        .content p {{ line-height: 1.7; color: #555; margin-bottom: 16px; }}
        .content code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
        .content pre {{ background: #1a1a2e; color: #eee; padding: 16px; border-radius: 8px;
                        overflow-x: auto; margin: 16px 0; font-size: 0.9rem; }}
        @media (max-width: 768px) {{
            body {{ flex-direction: column; }}
            .sidebar {{ width: 100%; height: auto; position: relative; }}
            .content {{ padding: 24px 16px; }}
        }}
    </style>
</head>
<body>
    <nav class="sidebar">
        <h2>{name}</h2>
        <div class="section">
            <div class="section-title">Getting Started</div>
            <a href="#" class="active">Introduction</a>
            <a href="#">Installation</a>
            <a href="#">Quick Start</a>
        </div>
        <div class="section">
            <div class="section-title">Guide</div>
            <a href="#">Configuration</a>
            <a href="#">Usage</a>
            <a href="#">Examples</a>
        </div>
        <div class="section">
            <div class="section-title">API Reference</div>
            <a href="#">Endpoints</a>
            <a href="#">Authentication</a>
            <a href="#">Errors</a>
        </div>
    </nav>
    <main class="content">
        <h1>Introduction</h1>
        <p class="subtitle">{description}</p>
        <p>Welcome to the {name} documentation. This guide will help you get started quickly.</p>
        <h2>Installation</h2>
        <p>Install the package using your preferred package manager:</p>
        <pre>pip install {name}</pre>
        <h2>Quick Start</h2>
        <p>Here's a minimal example to get you up and running:</p>
        <pre>from {name} import App\n\napp = App()\napp.run()</pre>
        <h2>Next Steps</h2>
        <p>Check out the <a href="#">Configuration</a> guide to customize your setup.</p>
    </main>
</body>
</html>""",
        },
    },
}
