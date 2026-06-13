'use client';

import { motion } from 'framer-motion';
import { slideInRight } from '@/motion/variants';
import styles from './QuoteBlock.module.css';

type Props = {
  quote: string;
  platform?: string;
  rating?: number;
  date?: string;
  linkedTheme: string;
  index?: number;
};

export function QuoteBlock({ quote, platform, rating, date, linkedTheme, index = 0 }: Props) {
  const stars = rating ? '★'.repeat(rating) + '☆'.repeat(5 - rating) : null;

  return (
    <motion.article
      className={styles.root}
      variants={slideInRight}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-40px' }}
      transition={{ delay: index * 0.08 }}
    >
      <blockquote className={styles.blockquote}>
        <span className={styles.openQuote} aria-hidden>&ldquo;</span>
        <p className={styles.text}>{quote}</p>
      </blockquote>
      <footer className={styles.attribution}>
        {platform && (
          <span className={styles.platform}>
            <span className="material-symbols-outlined" aria-hidden>
              {platform === 'App Store' ? 'phone_iphone' : 'android'}
            </span>
            {platform}
          </span>
        )}
        {stars && <span aria-label={`${rating} out of 5 stars`}>{stars}</span>}
        {date && <time>{date}</time>}
      </footer>
    </motion.article>
  );
}
