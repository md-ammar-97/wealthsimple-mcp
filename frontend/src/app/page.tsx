import Link from 'next/link';
import styles from './page.module.css';

const STEPS = [
  { icon: 'upload_file',  label: 'Import'   },
  { icon: 'policy',       label: 'Redact'   },
  { icon: 'category',     label: 'Classify' },
  { icon: 'leaderboard',  label: 'Select'   },
  { icon: 'format_quote', label: 'Quotes'   },
  { icon: 'lightbulb',    label: 'Actions'  },
  { icon: 'article',      label: 'Note'     },
  { icon: 'email',        label: 'Email'    },
];

export default function LandingPage() {
  return (
    <main className={styles.main}>
      <div className={styles.hero}>
        <h1 className={styles.headline}>
          Weekly Review Pulse<br />
          <span className={styles.brand}>for Wealthsimple Canada</span>
        </h1>
        <p className={styles.subtitle}>
          Turn 8–12 weeks of app reviews into a<br />
          250-word product insight note. Every week.
        </p>

        <Link href="/run" className={styles.cta}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>upload_file</span>
          Upload reviews.csv &rarr; Run pipeline
        </Link>

        <div className={styles.pipelineStrip}>
          {STEPS.map((s, i) => (
            <div key={s.label} className={styles.stepPill}>
              {i > 0 && <span className={styles.connector} aria-hidden />}
              <span className={`material-symbols-outlined ${styles.stepIcon}`}>{s.icon}</span>
              <span className={styles.stepLabel}>{s.label}</span>
            </div>
          ))}
        </div>

        <p className={styles.tagline}>
          Designed for&nbsp;
          <strong>Product</strong> &middot; <strong>Support</strong> &middot; <strong>Leadership</strong>
        </p>
      </div>
    </main>
  );
}
