import { defineConfig } from 'vitepress'
import { withMermaid } from "vitepress-plugin-mermaid";

export default withMermaid(
  defineConfig({
    title: 'MCP Composer',
    description: 'A FastAPI-based Composer that manages multiple MCP servers and tools',
    // Use the correct base URL for IBM GitHub Pages
    base: '/mcp-composer/',

    head: [
      ['link', { rel: 'icon', href: '/favicon.ico' }],
      ['meta', { name: 'theme-color', content: '#646cff' }],
      ['link', { rel: 'preload stylesheet', href: '/mcp-composer/assets/style.Cto_0cRC.css', as: 'style' }],
      ['link', { rel: 'preload stylesheet', href: '/mcp-composer/vp-icons.css', as: 'style' }],
    ],

    // Ignore dead links during development
    ignoreDeadLinks: true,

    themeConfig: {
      logo: '/logo.png',
      siteTitle: 'MCP Composer',

      nav: [
        { text: 'Home', link: '/' },
        { text: 'Guide', link: '/guide/' },
        { text: 'API', link: '/api/' },
        { text: 'Examples', link: '/examples/' },
        { text: 'GitHub', link: 'https://github.com/ibm/mcp-composer' }
      ],

      sidebar: {
        '/guide/': [
          {
            text: 'Getting Started',
            items: [
              { text: 'Introduction', link: '/guide/' },
              { text: 'Installation', link: '/guide/installation' },
              { text: 'Quick Start', link: '/guide/quick-start' },
              { text: 'Configuration', link: '/guide/configuration' },
              { text: 'Langflow Integration', link: '/guide/langflow-integration' },
              { text: 'Whl Usage', link: '/guide/use-with-claude' },
              { text: 'CLI Usage', link: '/guide/cli' },
              { text: 'Roadmap', link: '/guide/roadmap' },

            ]
          },
          {
            text: 'Core Concepts',
            items: [
              { text: 'Agent Management', link: '/guide/a2a' },
              { text: 'Server Management', link: '/guide/server-management' },
              { text: 'Tool Management', link: '/guide/tool-management' },
              { text: 'Prompt Management', link: '/guide/prompt-management' },
              { text: 'Resource Management', link: '/guide/resource-management' },
              { text: 'Catalog Composer', link: '/guide/catalog-composer' },
              { text: 'Catalog and Tool Tagging', link: '/guide/catalog-and-tool-tagging' },
              { text: 'Layered MCP Server', link: '/guide/layered_mcp_server' },
              { text: 'Tool Discovery Ranker', link: '/guide/tool-discovery-ranker' },
              { text: 'Tool Description Best Practices', link: '/guide/tool-description-best-practices' },
              { text: 'Authentication', link: '/guide/authentication' },
              { text: 'Policy Based ACL', link: '/guide/policy-acl' },
              { text: 'Middleware as Plugin', link: '/guide/middleware' },
              { text: 'Monitoring', link: '/guide/monitoring' },
              { text: 'Model Mesh Guide', link: '/guide/model_mesh' }
            ]
          }
        ],
        '/api/': [
          {
            text: 'API Reference',
            items: [
              { text: 'Overview', link: '/api/' }
            ]
          }
        ],
        '/examples/': [
          {
            text: 'Examples',
            items: [
              { text: 'Overview', link: '/examples/' },
              { text: 'MCP Inspector Demo', link: '/examples/mcp-inspector' },

              { text: 'Open API V2 fix', link: '/examples/using-swagger-2-api-spec' },
              { text: 'Claude Desktop Guide', link: '/examples/claude_desktop_guide' }
            ]
          }
          
        ]
      },

      socialLinks: [
        { icon: 'github', link: 'https://github.com/ibm/mcp-composer' }
      ],

      footer: {
        message: 'Released under the Apache License 2.0.',
        copyright: 'Copyright © IBM Corporation'
      },

      search: {
        provider: 'local'
      }
    },

    markdown: {
      theme: 'material-theme-palenight',
      lineNumbers: true
    },
    mermaid: {
      theme: 'base', // optional
      startOnLoad: true
    },
    mermaidPlugin: {
      class: 'mermaid-block' // optional
    }
  })
)