#!/bin/bash
set -e

# Step 1: Detect project root and set paths
if [ -f ".vitepress/config.ts" ]; then
  # You're inside the docs/ folder
  BUILD_CMD="vitepress build"
  DIST_DIR=".vitepress/dist"
else
  # You're in the project root
  BUILD_CMD="vitepress build docs"
  DIST_DIR="docs/.vitepress/dist"
fi

# Step 2: Clean previous build
rm -rf "$DIST_DIR"

# Step 3: Build site
echo "🔧 Building site..."
npx $BUILD_CMD

# Step 4: Prepare for GitHub Pages deployment
cd "$DIST_DIR"
touch .nojekyll

# Step 5: Deploy to gh-pages
git init
git add -A

COMMIT_MSG="🚀 Deploy VitePress docs - $(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "$COMMIT_MSG"

git push -f git@github.ibm.com:ai-elite/mcp-composer.git HEAD:gh-pages

# Step 6: Cleanup
cd -
rm -rf "$DIST_DIR/.git"

echo "✅ Deployed to: https://pages.github.ibm.com/ai-elite/mcp-composer/"

