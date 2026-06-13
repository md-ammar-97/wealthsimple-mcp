'use client';

import { motion } from 'framer-motion';
import { fadeUp } from '@/motion/variants';
import { RatingBar } from '@/components/RatingBar/RatingBar';
import { THEME_CODES, THEME_CATEGORIES, type ThemeCategory } from '@/types/pipeline';
import styles from './ThemeCard.module.css';

type Props = {
  rank: number;
  theme: string;
  reviewCount: number;
  avgRating: number;
};

export function ThemeCard({ rank, theme, reviewCount, avgRating }: Props) {
  const code = THEME_CODES[theme] ?? theme.slice(0, 3).toUpperCase();
  const category: ThemeCategory = THEME_CATEGORIES[theme] ?? 'technical';

  return (
    <motion.article
      className={`${styles.root} ${rank === 1 ? styles.top : ''}`}
      data-category={category}
      variants={fadeUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-32px' }}
      transition={{ delay: (rank - 1) * 0.07 }}
      whileHover={{ scale: 1.015, transition: { duration: 0.2 } }}
    >
      <header className={styles.header}>
        <span className={`${styles.badge} ${styles[`badge_${category}`]}`} title={theme}>
          {code}
        </span>
        <span className={styles.countChip}>#{rank} / {reviewCount} reviews</span>
      </header>

      <h3 className={styles.name}>{theme}</h3>

      <div className={styles.meta}>
        <span className={styles.avgRating}>
          avg {avgRating.toFixed(1)} ★
        </span>
      </div>

      <RatingBar avgRating={avgRating} />
    </motion.article>
  );
}
