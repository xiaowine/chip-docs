import os
import json
from pathlib import Path

def generate_sitemap(manifest_path: str, output_path: str) -> None:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    files = manifest.get("files", {})

    sitemap_content = "<!DOCTYPE html>\n<html>\n<head>\n<title>Site Map</title>\n</head>\n<body>\n"
    sitemap_content += "<h1>Site Map</h1>\n<ul>\n"

    for md5, path in files.items():
        sitemap_content += f'<li><a href="{path}">{path}</a></li>\n'

    sitemap_content += "</ul>\n</body>\n</html>"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sitemap_content)

    print(f"Site map generated at: {output_path}")

if __name__ == "__main__":
    manifest_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".data", "file-manifest.json"))
    output_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "sitemap.html"))
    generate_sitemap(manifest_path, output_path)