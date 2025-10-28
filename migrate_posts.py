#!/usr/bin/env python3
"""
Script to migrate Jekyll blog posts to Docusaurus format.
"""
import os
import yaml
from pathlib import Path
from datetime import datetime

# Input/output directories
jekyll_posts_dir = Path("/workspaces/gbb-blog/docs/_posts")
docusaurus_blog_dir = Path("/workspaces/gbb-blog/docusaurus/blog")

def parse_jekyll_post(file_path):
    """Parse a Jekyll post and extract frontmatter and content."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split frontmatter and content
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter_str = parts[1]
            body = parts[2].lstrip('\n')
            frontmatter = yaml.safe_load(frontmatter_str)
            return frontmatter, body
    
    return {}, content

def convert_post(jekyll_file):
    """Convert a Jekyll post to Docusaurus format."""
    frontmatter, body = parse_jekyll_post(jekyll_file)
    
    # Extract date and slug from filename
    filename = jekyll_file.stem  # Remove .md extension
    parts = filename.split('-', 3)
    
    if len(parts) >= 4:
        year, month, day = parts[0], parts[1], parts[2]
        slug = parts[3]
        date_str = f"{year}-{month}-{day}"
    else:
        return None
    
    # Create docusaurus frontmatter
    title = frontmatter.get('title', slug.replace('-', ' ').title())
    author = frontmatter.get('author', 'diego_casati')  # Default author
    tags = frontmatter.get('tags', [])
    description = frontmatter.get('description', '')
    
    # Build new frontmatter
    new_frontmatter = {
        'title': title,
        'description': description or title,
        'authors': [author],
        'tags': tags,
        'date': datetime.strptime(date_str, "%Y-%m-%d").date().isoformat(),
    }
    
    return {
        'frontmatter': new_frontmatter,
        'body': body,
        'date': date_str,
        'slug': slug,
    }

def migrate_posts():
    """Migrate all Jekyll posts to Docusaurus."""
    if not jekyll_posts_dir.exists():
        print(f"Jekyll posts directory not found: {jekyll_posts_dir}")
        return
    
    posts = list(jekyll_posts_dir.glob("*.md"))
    print(f"Found {len(posts)} posts to migrate")
    
    migrated = 0
    for post_file in posts:
        converted = convert_post(post_file)
        if converted:
            # Create directory for post
            post_dir = docusaurus_blog_dir / converted['date'] / converted['slug']
            post_dir.mkdir(parents=True, exist_ok=True)
            
            # Write frontmatter and body
            output_file = post_dir / "index.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                # Write YAML frontmatter
                f.write('---\n')
                yaml.dump(converted['frontmatter'], f, default_flow_style=False, allow_unicode=True)
                f.write('---\n\n')
                # Write body
                f.write(converted['body'])
            
            print(f"✓ Migrated: {post_file.name} -> {output_file}")
            migrated += 1
    
    print(f"\nSuccessfully migrated {migrated} posts!")

if __name__ == "__main__":
    migrate_posts()
