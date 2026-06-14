import Link from 'next/link';
import styles from './page.module.css';

export default function HomePage() {
  return (
    <main className={styles.main}>
      {/* Hero */}
      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <span className={`badge badge-blue ${styles.heroBadge}`}>
            AI-powered · Weekly cadence
          </span>
          <h1 className={styles.headline}>
            Turn app reviews into<br />
            <span className={styles.highlight}>product intelligence</span>
          </h1>
          <p className={styles.subtitle}>
            Review Pulse automatically scrapes, cleans, categorises, and summarises app store
            reviews into a weekly briefing — then drafts your stakeholder email.
          </p>

          <div className={styles.ctas}>
            <Link href="/analytics" className="btn btn-primary btn-lg">
              <span className="material-symbols-outlined">insights</span>
              View Wealthsimple Analytics
            </Link>
            <Link href="/upload" className="btn btn-default btn-lg">
              <span className="material-symbols-outlined">upload_file</span>
              Analyse Any App (CSV)
            </Link>
          </div>
        </div>

        {/* Pipeline strip */}
        <div className={styles.pipelineCard}>
          <p className={styles.pipelineLabel}>8-step AI pipeline</p>
          <div className={styles.steps}>
            {STEPS.map((s, i) => (
              <div key={s.label} className={styles.step}>
                {i > 0 && <span className={styles.arrow} aria-hidden>→</span>}
                <div className={styles.stepIcon}>
                  <span className="material-symbols-outlined">{s.icon}</span>
                </div>
                <span className={styles.stepLabel}>{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <section className={styles.features}>
        <div className="page-content">
          <div className={styles.featureGrid}>
            <FeatureCard
              href="/analytics"
              icon="analytics"
              badge="Automated"
              badgeClass="badge-green"
              title="Wealthsimple Analytics"
              description="Auto-scrapes Google Play reviews every Monday. Tracks sentiment trends, theme frequency, and rating changes over time. Delivers reports directly to Google Docs and Gmail."
              cta="View analytics →"
            />
            <FeatureCard
              href="/upload"
              icon="upload_file"
              badge="Self-serve"
              badgeClass="badge-blue"
              title="Analyse Any App"
              description="Upload a CSV of reviews from any app store. Enter your email and app name. The pipeline classifies, quotes, and actions — then emails you a formatted report."
              cta="Upload reviews →"
            />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className={styles.how}>
        <div className="page-content">
          <h2 className={styles.sectionTitle}>How it works</h2>
          <div className={styles.howGrid}>
            {HOW_ITEMS.map((item) => (
              <div key={item.step} className={styles.howItem}>
                <div className={styles.howStep}>{item.step}</div>
                <h3 className={styles.howTitle}>{item.title}</h3>
                <p className={styles.howDesc}>{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function FeatureCard({
  href, icon, badge, badgeClass, title, description, cta,
}: {
  href: string; icon: string; badge: string; badgeClass: string;
  title: string; description: string; cta: string;
}) {
  return (
    <Link href={href} className={styles.featureCard}>
      <div className={styles.featureTop}>
        <span className={`badge ${badgeClass}`}>{badge}</span>
        <span className={`material-symbols-outlined ${styles.featureIcon}`}>{icon}</span>
      </div>
      <h3 className={styles.featureTitle}>{title}</h3>
      <p className={styles.featureDesc}>{description}</p>
      <span className={styles.featureCta}>{cta}</span>
    </Link>
  );
}

const STEPS = [
  { icon: 'cloud_download', label: 'Fetch'    },
  { icon: 'policy',         label: 'Redact'   },
  { icon: 'category',       label: 'Classify' },
  { icon: 'leaderboard',    label: 'Rank'     },
  { icon: 'format_quote',   label: 'Quotes'   },
  { icon: 'lightbulb',      label: 'Actions'  },
  { icon: 'article',        label: 'Note'     },
  { icon: 'email',          label: 'Email'    },
];

const HOW_ITEMS = [
  { step: '01', title: 'Reviews scraped or uploaded', desc: 'For Wealthsimple, reviews are automatically fetched from Google Play every Monday. For any other app, upload a CSV.' },
  { step: '02', title: 'PII redacted & classified',   desc: 'Personal data is stripped before any LLM sees it. Reviews are then classified into 3–5 recurring themes.' },
  { step: '03', title: 'Quotes & actions selected',   desc: 'A verified verbatim quote is chosen per theme. Three concrete product actions are generated from the top themes.' },
  { step: '04', title: 'Report delivered',            desc: 'A 250-word pulse note and stakeholder email are created. For Wealthsimple: saved to Google Docs and drafted in Gmail.' },
];
