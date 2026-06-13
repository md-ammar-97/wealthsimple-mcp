'use client';

import { motion } from 'framer-motion';
import { fadeUp } from '@/motion/variants';
import styles from './ActionCard.module.css';

type Props = {
  index: number;
  action: string;
  linkedTheme: string;
};

export function ActionCard({ index, action, linkedTheme }: Props) {
  return (
    <motion.article
      className={styles.root}
      variants={fadeUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-32px' }}
      transition={{ delay: (index - 1) * 0.07 }}
    >
      <div className={styles.header}>
        <span className={styles.number} aria-hidden>
          {String(index).padStart(2, '0')}
        </span>
        <span className={styles.theme}>{linkedTheme}</span>
      </div>
      <p className={styles.body}>{action}</p>
    </motion.article>
  );
}
