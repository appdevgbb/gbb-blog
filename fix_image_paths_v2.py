#!/usr/bin/env python3
"""
Fix image paths in migrated blog posts - version 2.
"""
import re
from pathlib import Path

docusaurus_blog_dir = Path("/workspaces/gbb-blog/docusaurus/blog")

def fix_image_paths_v2():
    """Fix image paths in all migrated posts."""
    # Find all markdown files
    md_files = list(docusaurus_blog_dir.glob("**/index.md"))
    
    print(f"Found {len(md_files)} markdown files to process")
    
    updated = 0
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Get the post directory to understand structure
        # e.g., /workspaces/gbb-blog/docusaurus/blog/2024-11-05/afd-aks-ingress-tls/index.md
        post_dir = md_file.parent
        post_slug = post_dir.name
        date_dir = post_dir.parent
        date = date_dir.name
        
        # Find any references to image directories or files
        # Pattern: /assets/img/YYYY-MM-DD-slug/filename
        
        # Build list of image directories that exist
        img_dirs = set()
        for img_dir in docusaurus_blog_dir.glob("20*/"):
            if img_dir.is_dir() and not any(c.isalpha() for c in img_dir.name):
                # This is a date directory
                continue
            if img_dir.is_dir():
                img_dirs.add(img_dir.name)
        
        # Now replace paths
        for img_dir_name in img_dirs:
            # Replace /assets/img/YYYY-MM-DD-slug/filename with ./filename
            pattern = rf'/assets/img/{re.escape(img_dir_name)}/([^)\]]*)'
            replacement = r'./\1'
            content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Fixed: {md_file.relative_to(docusaurus_blog_dir)}")
            updated += 1
    
    print(f"\nUpdated {updated} files")

if __name__ == "__main__":
    fix_image_paths_v2()
