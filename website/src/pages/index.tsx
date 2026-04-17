import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';

export default function Home(): React.JSX.Element {
  const { siteConfig } = useDocusaurusContext();
  const logoUrl = useBaseUrl('/img/company-logo.svg');

  return (
    <Layout title={siteConfig.title} description={siteConfig.tagline}>
      <main className="homePage">
        <section className="hero hero--primary homeHero">
          <div className="container">
            <img className="homeHeroLogo" src={logoUrl} alt="Linetec Services logo" />
            <h1 className="hero__title">{siteConfig.title}</h1>
            <p className="hero__subtitle">{siteConfig.tagline}</p>
            <div className="homeHeroActions">
              <Link className="button button--secondary button--lg" to="/docs/">
                Open Runbook
              </Link>
              <Link className="button button--outline button--lg" to="/blog">
                View Change Log
              </Link>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
