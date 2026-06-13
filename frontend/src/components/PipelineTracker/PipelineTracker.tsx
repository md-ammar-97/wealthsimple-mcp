'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { scaleIn, pipelineStep } from '@/motion/variants';
import type { PipelineStep } from '@/types/pipeline';
import styles from './PipelineTracker.module.css';

type Props = { steps: PipelineStep[]; };

function StepIcon({ step }: { step: PipelineStep }) {
  if (step.state === 'done') {
    return (
      <motion.span
        key="check"
        className={`${styles.icon} material-symbols-outlined`}
        variants={scaleIn}
        initial="hidden"
        animate="visible"
      >
        check_circle
      </motion.span>
    );
  }
  if (step.state === 'error') {
    return <span className={`${styles.icon} ${styles.iconError} material-symbols-outlined`}>cancel</span>;
  }
  if (step.state === 'active') {
    return (
      <motion.span
        className={`${styles.icon} material-symbols-outlined`}
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, ease: 'linear', duration: 1 }}
      >
        {step.icon}
      </motion.span>
    );
  }
  return <span className={`${styles.icon} material-symbols-outlined`}>{step.icon}</span>;
}

function Step({ step, isLast }: { step: PipelineStep; isLast: boolean }) {
  const isDone    = step.state === 'done';
  const isActive  = step.state === 'active';
  const isError   = step.state === 'error';

  return (
    <li className={styles.stepItem} aria-current={isActive ? 'step' : undefined}>
      <div className={styles.stepBody}>
        <motion.div
          className={`${styles.iconWrap} ${styles[`state_${step.state}`]}`}
          animate={isActive ? 'active' : isDone ? 'done' : 'idle'}
          variants={pipelineStep}
        >
          {isActive && (
            <motion.div
              className={styles.glowRing}
              animate={{ opacity: [0.6, 1, 0.6] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
            />
          )}
          <AnimatePresence mode="wait">
            <StepIcon key={step.state} step={step} />
          </AnimatePresence>
        </motion.div>
        <div className={styles.labelWrap}>
          <span className={styles.label}>{step.label}</span>
          {step.detail && (
            <span className={`${styles.detail} ${isError ? styles.detailError : ''}`}>
              {step.detail}
            </span>
          )}
        </div>
      </div>
      {!isLast && (
        <div className={styles.connector} aria-hidden>
          <motion.div
            className={styles.connectorFill}
            initial={{ scaleX: 0 }}
            animate={{ scaleX: isDone ? 1 : 0 }}
            transition={{ duration: 0.4, ease: [0.05, 0.7, 0.1, 1.0] }}
            style={{ transformOrigin: 'left center' }}
          />
        </div>
      )}
    </li>
  );
}

export function PipelineTracker({ steps }: Props) {
  return (
    <nav aria-label="Pipeline steps">
      <ol className={styles.rail}>
        {steps.map((step, i) => (
          <Step key={step.id} step={step} isLast={i === steps.length - 1} />
        ))}
      </ol>
    </nav>
  );
}
