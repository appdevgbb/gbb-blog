#!/usr/bin/env python3
"""
Post-migration script to fix image paths in migrated blog posts.
"""
import re
from pathlib import Path

docusaurus_blog_dir = Path("/workspaces/gbb-blog/docusaurus/blog")

def fix_image_paths():
    """Fix image paths in all migrated posts."""
    # Find all markdown files
    md_files = list(docusaurus_blog_dir.glob("**/index.md"))
    
    print(f"Found {len(md_files)} markdown files to process")
    
    updated = 0
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix image paths: /assets/img/YYYY-MM-DD-slug/ -> ./
        # Replace Jekyll image paths with relative paths for Docusaurus
        content = re.sub(
            r'!\[(.*?)\]\(/assets/img/([^/]+)/([^)]*)\)',
            r'![\1](..\/..\/' + r'2' + r'/\3)',
            content
        )
        
        # Also handle the directory name mapping
        for img_dir in docusaurus_blog_dir.glob("20*/"):
            if img_dir.is_dir():
                dir_name = img_dir.name
                # Map the pattern more carefully
                pattern = rf'!\[(.*?)\]\(/assets/img/{dir_name}/([^)]*)\)'
                replacement = r'![\1](./\2)'
                content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Fixed: {md_file.relative_to(docusaurus_blog_dir)}")
            updated += 1
    
    print(f"\nUpdated {updated} files")

if __name__ == "__main__":
    fix_image_paths()
