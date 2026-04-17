import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Weekly PDFs Runbook',
  tagline: 'Living documentation for the Smartsheet Weekly PDF Generator',
  favicon: 'img/favicon.ico',

  url: process.env.DOCS_SITE_URL ?? 'https://weekly-pdfs-runbook.vercel.app',
  baseUrl: '/',

  // Must match vercel.json's `"trailingSlash": false`. If these disagree, the
  // Docusaurus router emits canonical URLs with a trailing slash while Vercel
  // 308s to the non-slashed path — landing on a route the client router then
  // renders as "Page Not Found".
  trailingSlash: false,

  organizationName: 'jflo21',
  projectName: 'generate-weekly-pdfs-dsr-resiliency',

  onBrokenLinks: 'warn',

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/jflo21/generate-weekly-pdfs-dsr-resiliency/edit/master/website/',
          showLastUpdateAuthor: true,
          showLastUpdateTime: true,
        },
        blog: {
          showReadingTime: true,
          blogTitle: 'Change Log',
          blogDescription:
            'Auto-generated runbook entries for every merge to master.',
          postsPerPage: 10,
          blogSidebarTitle: 'Recent merges',
          blogSidebarCount: 'ALL',
          feedOptions: {
            type: ['rss', 'atom'],
            title: 'Weekly PDFs Change Log',
            description: 'Per-merge runbook entries for the repo.',
          },
          editUrl:
            'https://github.com/jflo21/generate-weekly-pdfs-dsr-resiliency/edit/master/website/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // `image: 'img/social-card.png'` would populate og:image for rich link
    // previews. Add once website/static/img/social-card.png exists.
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Weekly PDFs Runbook',
      logo: {
        alt: 'Linetec Services — A Centuri Company',
        src: 'img/logo.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'runbookSidebar',
          position: 'left',
          label: 'Runbook',
        },
        { to: '/blog', label: 'Change Log', position: 'left' },
        {
          href: 'https://github.com/jflo21/generate-weekly-pdfs-dsr-resiliency',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Runbook',
          items: [
            { label: 'Overview', to: '/docs' },
            { label: 'Workflows', to: '/docs/runbook/workflows' },
            { label: 'Python modules', to: '/docs/runbook/python-modules' },
          ],
        },
        {
          title: 'Project',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/jflo21/generate-weekly-pdfs-dsr-resiliency',
            },
            { label: 'Change Log', to: '/blog' },
          ],
        },
      ],
      copyright: `© ${new Date().getFullYear()} Linetec Services — A Centuri Company. Generated with Docusaurus, updated on every merge to master.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'python', 'yaml', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
