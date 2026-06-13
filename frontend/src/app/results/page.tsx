'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fadeUp, staggerChildren } from '@/motion/variants';
import { RunSummaryChip } from '@/components/RunSummaryChip/RunSummaryChip';
import { PulseNoteBanner } from '@/components/PulseNoteBanner/PulseNoteBanner';
import { ThemeCard } from '@/components/ThemeCard/ThemeCard';
import { QuoteBlock } from '@/components/QuoteBlock/QuoteBlock';
import { ActionCard } from '@/components/ActionCard/ActionCard';
import { EmailPreview } from '@/components/EmailPreview/EmailPreview';
import { ThemeLegendDrawer } from '@/components/ThemeLegendDrawer/ThemeLegendDrawer';
import type { RunResult } from '@/types/pipeline';
import styles from './results.module.css';

export default function ResultsPage() {
  const [result, setResult] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    fetch('/api/results')
      .then(r => {
        if (!r.ok) throw new Error('Results not found — run the pipeline first.');
        return r.json();
      })
      .then(setResult)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--md-sys-color-primary)', animation: 'spin 1s linear infinite' }}>
          progress_activity
        </span>
        <p>Loading results…</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className={styles.errorState}>
        <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--md-sys-color-error)' }}>error</span>
        <p>{error ?? 'No results available.'}</p>
        <a href="/run" className={styles.runLink}>Go to Run page →</a>
      </div>
    );
  }

  return (
    <main className={styles.main}>
      <header className={styles.stickyHeader}>
        <a href="/run" className={styles.backLink}>
          <span className="material-symbols-outlined">arrow_back</span>
          Back to Run
        </a>
        <RunSummaryChip result={result} />
        <div className={styles.headerActions}>
          <button className={styles.legendBtn} onClick={() => setDrawerOpen(true)} aria-label="Open theme legend">
            <span className="material-symbols-outlined">legend_toggle</span>
            Theme Legend
          </button>
          <button className={styles.exportBtn} onClick={() => window.print()} aria-label="Export PDF">
            <span className="material-symbols-outlined">print</span>
            Export PDF
          </button>
        </div>
      </header>

      <div className={styles.content}>
        {/* Pulse Note */}
        <PulseNoteBanner result={result} />

        {/* Top Themes */}
        <section className={styles.section} aria-labelledby="themes-heading">
          <h2 id="themes-heading" className={styles.sectionTitle}>Top Themes</h2>
          <motion.div
            className={styles.themeGrid}
            variants={staggerChildren}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-32px' }}
          >
            {result.themes.map(t => (
              <ThemeCard
                key={t.theme}
                rank={t.rank}
                theme={t.theme}
                reviewCount={t.reviewCount}
                avgRating={t.avgRating}
              />
            ))}
          </motion.div>
        </section>

        {/* Quotes */}
        <section className={styles.section} aria-labelledby="quotes-heading">
          <h2 id="quotes-heading" className={styles.sectionTitle}>Real User Quotes</h2>
          <motion.div
            className={styles.quoteList}
            variants={staggerChildren}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-32px' }}
          >
            {result.quotes.map((q, i) => (
              <QuoteBlock
                key={i}
                quote={q.quote}
                platform={q.platform as 'App Store' | 'Google Play' ?? 'App Store'}
                rating={q.rating ?? 3}
                date={q.date ?? ''}
                linkedTheme={q.theme}
                index={i}
              />
            ))}
          </motion.div>
        </section>

        {/* Actions */}
        <section className={styles.section} aria-labelledby="actions-heading">
          <h2 id="actions-heading" className={styles.sectionTitle}>Action Ideas</h2>
          <motion.div
            className={styles.actionGrid}
            variants={staggerChildren}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-32px' }}
          >
            {result.actions.map((a, i) => (
              <ActionCard key={i} index={i + 1} action={a.action} linkedTheme={a.linkedTheme} />
            ))}
          </motion.div>
        </section>

        {/* Email */}
        <section className={styles.section} aria-labelledby="email-heading">
          <h2 id="email-heading" className={styles.sectionTitle}>Email Draft</h2>
          <EmailPreview emailText={result.emailText} />
        </section>
      </div>

      <ThemeLegendDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </main>
  );
}
