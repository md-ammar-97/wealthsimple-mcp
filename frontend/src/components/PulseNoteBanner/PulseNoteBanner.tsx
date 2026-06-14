'use client';

import { motion } from 'framer-motion';
import { fadeUp } from '@/motion/variants';
import { useClipboard } from '@/hooks/useClipboard';
import type { RunResult } from '@/types/pipeline';
import styles from './PulseNoteBanner.module.css';

type Props = { result: RunResult; };

export function PulseNoteBanner({ result }: Props) {
  const { copy, copied } = useClipboard();

  const topThemes   = (result.themes  ?? []).slice(0, 3);
  const topQuotes   = (result.quotes  ?? []).slice(0, 3);
  const topActions  = (result.actions ?? []).slice(0, 3);

  return (
    <motion.section
      className={styles.root}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      aria-label="Weekly pulse note"
    >
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>Wealthsimple Canada — Weekly Review Pulse</h2>
          <p className={styles.meta}>
            Period: {result.periodStart} to {result.periodEnd} &middot; {result.reviewCount} reviews analysed
          </p>
        </div>
        <div className={styles.actions}>
          <button
            className={styles.exportBtn}
            onClick={() => window.print()}
            title="Export as PDF"
          >
            <span className="material-symbols-outlined">print</span>
            Export PDF
          </button>
        </div>
      </header>

      <div className={styles.grid}>
        <div className={styles.col}>
          <h3 className={styles.colTitle}>Top Themes</h3>
          <ol className={styles.themeList}>
            {topThemes.map((t, i) => (
              <li key={t.theme} className={styles.themeRow}>
                <span className={styles.rank}>{i + 1}.</span>
                <span className={styles.themeName}>{t.theme}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className={styles.col}>
          <h3 className={styles.colTitle}>Real User Quotes</h3>
          <ul className={styles.quoteList}>
            {topQuotes.map((q, i) => (
              <li key={i} className={styles.quoteRow}>
                &ldquo;{q.quote.length > 80 ? q.quote.slice(0, 78) + '…' : q.quote}&rdquo;
              </li>
            ))}
          </ul>
        </div>

        <div className={styles.col}>
          <h3 className={styles.colTitle}>Action Ideas</h3>
          <ol className={styles.actionList}>
            {topActions.map((a, i) => (
              <li key={i} className={styles.actionRow}>
                <span className={styles.rank}>{i + 1}.</span>
                <span>{a.action.length > 80 ? a.action.slice(0, 78) + '…' : a.action}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <footer className={styles.footer}>
        <span>{result.wordCount} words</span>
        {result.generatedAt && <span>Generated: {result.generatedAt.split('T')[0]}</span>}
        {result.lowDataWarning && (
          <span className={styles.warning}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle' }}>warning</span>
            &nbsp;Low data — results may be incomplete
          </span>
        )}
      </footer>

      <button
        className={`${styles.copyFab} ${copied ? styles.copied : ''}`}
        onClick={() => copy(result.noteText)}
        aria-label="Copy pulse note to clipboard"
        title="Copy note"
      >
        <span className="material-symbols-outlined">{copied ? 'check' : 'content_copy'}</span>
      </button>
    </motion.section>
  );
}
