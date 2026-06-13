'use client';

import { useEffect, useState } from 'react';
import type { RunResult } from '@/types/pipeline';
import styles from './note.module.css';

export default function NotePage() {
  const [result, setResult] = useState<RunResult | null>(null);

  useEffect(() => {
    fetch('/api/results')
      .then(r => r.ok ? r.json() : null)
      .then(setResult);
  }, []);

  if (!result) return null;

  return (
    <main className={styles.main}>
      <article className={styles.note}>
        <header className={styles.header}>
          <h1 className={styles.title}>Wealthsimple Canada — Weekly Review Pulse</h1>
          <p className={styles.meta}>
            Period: {result.periodStart} to {result.periodEnd} &middot; {result.reviewCount} reviews analysed
          </p>
        </header>
        <pre className={styles.body}>{result.noteText}</pre>
        <footer className={styles.footer}>
          Generated: {result.generatedAt?.split('T')[0]} &middot; Wealthsimple Canada &middot; Weekly Review Pulse
        </footer>
      </article>
      <div className={styles.printHint}>
        <button onClick={() => window.print()} className={styles.printBtn}>
          <span className="material-symbols-outlined">print</span>
          Print / Export PDF
        </button>
      </div>
    </main>
  );
}
