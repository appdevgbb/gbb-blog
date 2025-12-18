import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'Azure Global Black Belt',
  tagline: 'Home for the Azure Global Black Belt team to share knowledge',
  favicon: 'img/gbb.png',
  
  headTags: [
    {
      tagName: 'meta',
      attributes: {
        name: 'og:title',
        content: 'Azure Global Black Belt',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'og:description',
        content: 'Home for the Azure Global Black Belt team to share knowledge',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'og:image',
        content: 'https://azureglobalblackbelts.com/img/gbb.png',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'og:type',
        content: 'website',
      },
    },
  ],

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://azureglobalblackbelts.com',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'appdevgbb', // Usually your GitHub org/user name.
  projectName: 'gbb-blog', // Usually your repo name.

  onBrokenLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: false,
        blog: {
          routeBasePath: '/',
          showReadingTime: true,
          blogSidebarCount: 'ALL', // Show all posts in sidebar
          blogSidebarTitle: 'All Posts',
          postsPerPage: 10, // Show 10 posts per page
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/appdevgbb/gbb-blog/tree/main/docusaurus/',
          // Useful options to enforce blogging best practices
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  // Enable Mermaid diagram support
  markdown: {
    mermaid: true,
  },

  themeConfig: {
    // Replace with your project's social card
    image: 'img/gbb.png',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Azure Global Black Belt',
      logo: {
        alt: 'Azure Global Black Belt Logo',
        src: 'img/gbb.png',
      },
      items: [
        {
          to: '/',
          position: 'left',
          label: 'Blog',
        },
        {
          href: 'https://www.youtube.com/@AzureGlobalBlackBelt',
          label: 'YouTube',
          position: 'right',
        },
        {
          href: 'https://github.com/appdevgbb',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Posts',
          items: [
            {
              label: 'Posts',
              to: '/gbb-blog',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/appdevgbb',
            },
            {
              label: 'Microsoft Learn',
              href: 'https://learn.microsoft.com/azure/',
            },
            {
              label: 'Azure Blog',
              href: 'https://azure.microsoft.com/blog/',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'Twitter',
              href: 'https://twitter.com/stevegriffith',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Azure Global Black Belt. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bicep', 'bash', 'powershell', 'json', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,

  themes: [
    '@docusaurus/theme-mermaid',
    [
      "@easyops-cn/docusaurus-search-local",
      {
        hashed: true,
        language: ["en"],
        highlightSearchTermsOnTargetPage: true,
        explicitSearchResultPath: true,
        blogRouteBasePath: '/',
        docsRouteBasePath: [],
        indexBlog: true,
        indexDocs: false,
      },
    ],
  ],
};

export default config;
