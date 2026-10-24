# MCP Composer Documentation

This directory contains the documentation for MCP Composer, built with [VitePress](https://vitepress.dev/).

## Quick Start

### Prerequisites

- Node.js 24+ 
- npm or yarn

### Development

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start development server**:
   ```bash
   npm run docs:dev
   ```

3. **Open browser**: Navigate to `http://localhost:5173`

### Build

```bash
npm run docs:build
```

### Preview Production Build

```bash
npm run docs:preview
```

## Project Structure

```
docs/
├── .vitepress/
│   └── config.ts          # VitePress configuration
├── guide/                 # User guides
├── cookbook/              # Task recipes. Programs live in example/cookbook/
├── api/                   # API documentation
├── examples/              # Code examples
├── public/                # Static assets
├── index.md              # Homepage
└── package.json          # Dependencies
```

## Writing Documentation

### Adding New Pages

1. Create a new `.md` file in the appropriate directory
2. Add frontmatter with title and description
3. Update the sidebar configuration in `.vitepress/config.ts`

### Frontmatter Example

```markdown
---
title: Page Title
description: Page description
---

# Page Content
```

### Code Blocks

Use syntax highlighting for code blocks:

````markdown
```python
def example():
    return "Hello World"
```
````

### Links

Use relative paths for internal links:

```markdown
[Installation Guide](/guide/installation)
[API Reference](/api/)
```

## Configuration

### VitePress Config

The main configuration is in `.vitepress/config.ts`:

- **Site settings**: Title, description, base URL
- **Navigation**: Top navigation bar
- **Sidebar**: Left sidebar navigation
- **Theme**: Custom theme settings
- **Plugins**: VitePress plugins

### Customization

- **Styling**: Modify CSS in `.vitepress/theme/`
- **Components**: Add Vue components in `.vitepress/theme/`
- **Plugins**: Configure VitePress plugins

## Deployment

### GitHub Pages

Publish the site, including the cookbook, with `deploy.sh`. The script installs the docs dependencies, runs `npm run docs:build`, and pushes `.vitepress/dist` to the `gh-pages` branch.

The site is https://ibm.github.io/mcp-composer/

### Manual Deployment

```bash
# Build the site
npm run docs:build

# Deploy to any static hosting service
# Copy contents of .vitepress/dist/ to your hosting provider
```



### Style Guide

- Use **bold** for emphasis
- Use `code` for inline code
- Use headings for structure
- Include code examples
- Add links to related pages

## Troubleshooting

### Common Issues

#### Build Errors

```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

#### Development Server Issues

```bash
# Check port availability
lsof -i :5173

# Use different port
npm run docs:dev -- --port 3000
```

#### Deployment Issues

- Check GitHub Actions logs
- Verify repository settings
- Ensure `gh-pages` branch exists

## Resources

- [VitePress Documentation](https://vitepress.dev/)
- [Markdown Guide](https://www.markdownguide.org/)
- [GitHub Pages](https://pages.github.com/)

## Deploy on the github repo 

1. go to the docs folder 

```
cd docs
```

2. Install nodejs dependencies

```
npm install
```

3. Build the site

```      
npm run docs:build
```
chek if there is any error in the console or not if not


4. Publish the site, including the cookbook

```
./deploy.sh
```

That pushes the built site to `gh-pages` on the public repository.