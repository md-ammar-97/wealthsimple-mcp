'use client';

import { motion } from 'framer-motion';
import styles from './RatingBar.module.css';

type Props = { avgRating: number };

const STARS = [5, 4, 3, 2, 1] as const;
const FAKE_DIST: Record<number, number[]> = {
  5: [0.50, 0.25, 0.12, 0.08, 0.05],
  4: [0.35, 0.30, 0.15, 0.12, 0.08],
  3: [0.20, 0.20, 0.25, 0.20, 0.15],
  2: [0.10, 0.15, 0.20, 0.30, 0.25],
  1: [0.05, 0.08, 0.12, 0.25, 0.50],
};

export function RatingBar({ avgRating }: Props) {
  const rounded = Math.max(1, Math.min(5, Math.round(avgRating)));
  const dist = FAKE_DIST[rounded];

  return (
    <div className={styles.root} aria-label={`Average rating ${avgRating.toFixed(1)} out of 5`}>
      {STARS.map((star, i) => (
        <div key={star} className={styles.row}>
          <span className={styles.label} aria-hidden>{'★'.repeat(star)}{'☆'.repeat(5 - star)}</span>
          <div className={styles.track}>
            <motion.div
              className={styles.fill}
              style={{ '--rating-color': `var(--color-rating-${star})` } as React.CSSProperties}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: dist[i] }}
              transition={{ duration: 0.5, ease: [0.05, 0.7, 0.1, 1.0], delay: i * 0.04 }}
              aria-valuenow={Math.round(dist[i] * 100)}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <span className={styles.pct}>{Math.round(dist[i] * 100)}%</span>
        </div>
      ))}
    </div>
  );
}
