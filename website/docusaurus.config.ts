import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Weekly PDFs Runbook',
  tagline: 'Living documentation for the Smartsheet Weekly PDF Generator',
  // Add `favicon: 'img/favicon.ico'` (and create website/static/img/favicon.ico)
  // once branding assets exist. Docusaurus uses a sensible default without it.

  url: process.env.DOCS_SITE_URL ?? 'https://weekly-pdfs-runbook.vercel.app',
  baseUrl: '/',

  organizationName: 'jflo21',
  projectName: 'generate-weekly-pdfs-dsr-resiliency',

  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

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
    navbar: {
      title: 'Weekly PDFs Runbook',
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
            { label: 'Overview', to: '/docs/' },
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
      copyright: `Generated with Docusaurus. Updated automatically on every merge to master.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'python', 'yaml', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
