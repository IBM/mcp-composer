import { defineConfig } from 'vitepress'
import { withMermaid } from "vitepress-plugin-mermaid";

export default withMermaid(
  defineConfig({
    title: 'MCP Composer',
    description: 'A FastMCP-based composer that manages multiple MCP servers and tools',
    // Use the correct base URL for GitHub Pages
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
              { text: 'CLI', link: '/guide/cli' }
            ]
          },
          {
            text: 'Compose',
            items: [
              { text: 'Servers', link: '/guide/server-management' },
              { text: 'Tools', link: '/guide/tool-management' },
              { text: 'Prompts', link: '/guide/prompt-management' },
              { text: 'Resources', link: '/guide/resource-management' },
              { text: 'Authentication', link: '/guide/authentication' },
              { text: 'Middleware', link: '/guide/middleware' }
            ]
          },
          {
            text: 'Catalog and discovery',
            items: [
              { text: 'Catalog', link: '/guide/catalog-management' },
              { text: 'Skills', link: '/guide/skill-management' },
              { text: 'Workflows', link: '/guide/workflow-management' },
              { text: 'Catalog composer', link: '/guide/catalog-composer' },
              { text: 'Think composer', link: '/guide/think-composer' },
              { text: 'Layered servers', link: '/guide/layered_mcp_server' },
              { text: 'Tool discovery', link: '/guide/tool-discovery-ranker' },
              { text: 'Tool descriptions', link: '/guide/tool-description-best-practices' }
            ]
          },
          {
            text: 'Operations',
            items: [
              { text: 'Agents (A2A)', link: '/guide/a2a' },
              { text: 'Policy', link: '/guide/policy-acl' },
              { text: 'Monitoring', link: '/guide/monitoring' },
              { text: 'Model mesh', link: '/guide/model_mesh' }
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
              { text: 'MCP Inspector', link: '/examples/mcp-inspector' },
              { text: 'OpenAPI 2 to 3', link: '/examples/using-swagger-2-api-spec' }
            ]
          }
          
        ]
      },

      socialLinks: [
        { icon: 'github', link: 'https://github.com/ibm/mcp-composer' }
      ],

      footer: {
        message: 'Released under the Apache License 2.0.',
        copyright: ''
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