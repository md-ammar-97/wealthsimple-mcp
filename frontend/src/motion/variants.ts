import type { Variants } from 'framer-motion';

export const fadeUp: Variants = {
  hidden:  { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0,  transition: { duration: 0.4, ease: [0.05, 0.7, 0.1, 1.0] } },
  exit:    { opacity: 0, y: -8, transition: { duration: 0.2, ease: [0.3, 0, 0.8, 0.15] } },
};

export const staggerChildren: Variants = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.07 } },
};

export const scaleIn: Variants = {
  hidden:  { opacity: 0, scale: 0.94 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.35, ease: [0.05, 0.7, 0.1, 1.0] } },
};

export const slideInRight: Variants = {
  hidden:  { opacity: 0, x: 32 },
  visible: { opacity: 1, x: 0,  transition: { duration: 0.45, ease: [0.05, 0.7, 0.1, 1.0] } },
  exit:    { opacity: 0, x: -24, transition: { duration: 0.2, ease: [0.3, 0, 0.8, 0.15] } },
};

export const pipelineStep: Variants = {
  idle:   { scale: 1,    opacity: 0.5 },
  active: { scale: 1.02, opacity: 1,  transition: { duration: 0.3, ease: [0.05, 0.7, 0.1, 1.0] } },
  done:   { scale: 1,    opacity: 1,  transition: { duration: 0.2 } },
  error:  { scale: 1,    opacity: 1,  transition: { duration: 0.2 } },
};
