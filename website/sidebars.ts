import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  runbookSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Runbook',
      collapsed: false,
      items: [
        'runbook/overview',
        'runbook/python-modules',
        'runbook/workflows',
        'runbook/portals',
        'runbook/scripts',
        'runbook/operations',
        'runbook/auth-rbac-bootstrap',
        'runbook/vercel-deployment',
        'runbook/whats-new',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      collapsed: true,
      items: ['reference/environment', 'reference/how-this-site-updates'],
    },
  ],
};

export default sidebars;
