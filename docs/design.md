# Design System — Wealthsimple App Review Insights Analyser

## Stack & Philosophy

| Layer | Choice |
|---|---|
| Framework | Next.js 15 (App Router) |
| Bundler | Vite (via `@vitejs/plugin-react`) |
| Styling | CSS Modules + CSS custom properties (no Tailwind) |
| Animation | Framer Motion 11 |
| Icons | Material Symbols (variable font) |
| Design system | Google Material Design 3 (M3) |
| Fonts | Google Fonts — `Inter` (body), `DM Serif Display` (hero/headlines) |

**Philosophy:** The UI is a _reading surface_, not an analytics dashboard. Inspired by M3's emphasis on expressive typography, tonal colour surfaces, and purposeful motion. Every screen exists to help a busy stakeholder read faster — not to impress with charts.

---

## 1. Colour System (M3 Dynamic Colour)

### 1.1 Source Colour

```css
/* Seed colour — Wealthsimple brand green */
--md-source: #00C086;
```

M3 generates a complete tonal palette from this seed using HCT colour space. The palette below is the generated output.

### 1.2 Light Scheme Tokens

```css
:root {
  /* Primary */
  --md-sys-color-primary:             #006B4B;
  --md-sys-color-on-primary:          #FFFFFF;
  --md-sys-color-primary-container:   #7DF8C3;
  --md-sys-color-on-primary-container:#00210F;

  /* Secondary */
  --md-sys-color-secondary:           #4D6359;
  --md-sys-color-on-secondary:        #FFFFFF;
  --md-sys-color-secondary-container: #CFE9DC;
  --md-sys-color-on-secondary-container: #0A1F17;

  /* Tertiary — accent warm */
  --md-sys-color-tertiary:            #3E6374;
  --md-sys-color-on-tertiary:         #FFFFFF;
  --md-sys-color-tertiary-container:  #C2E8FC;
  --md-sys-color-on-tertiary-container: #001F2B;

  /* Error */
  --md-sys-color-error:               #BA1A1A;
  --md-sys-color-on-error:            #FFFFFF;
  --md-sys-color-error-container:     #FFDAD6;
  --md-sys-color-on-error-container:  #410002;

  /* Surface */
  --md-sys-color-surface:             #F5FBF6;
  --md-sys-color-on-surface:          #171D1A;
  --md-sys-color-surface-variant:     #DBE5DE;
  --md-sys-color-on-surface-variant:  #404944;
  --md-sys-color-surface-container-lowest:  #FFFFFF;
  --md-sys-color-surface-container-low:     #EFF5F0;
  --md-sys-color-surface-container:         #E9EFEb;
  --md-sys-color-surface-container-high:    #E4EAE5;
  --md-sys-color-surface-container-highest: #DEE4DF;

  /* Outline */
  --md-sys-color-outline:             #707974;
  --md-sys-color-outline-variant:     #BFC9C2;

  /* Inverse */
  --md-sys-color-inverse-surface:     #2B322E;
  --md-sys-color-inverse-on-surface:  #ECF2ED;
  --md-sys-color-inverse-primary:     #60DB9E;
}
```

### 1.3 Dark Scheme Tokens

```css
[data-theme="dark"] {
  --md-sys-color-primary:             #60DB9E;
  --md-sys-color-on-primary:          #003824;
  --md-sys-color-primary-container:   #005137;
  --md-sys-color-on-primary-container:#7DF8C3;

  --md-sys-color-surface:             #0F1511;
  --md-sys-color-on-surface:          #DEE4DF;
  --md-sys-color-surface-container-lowest:  #0A0F0C;
  --md-sys-color-surface-container-low:     #171D1A;
  --md-sys-color-surface-container:         #1B2120;
  --md-sys-color-surface-container-high:    #262B28;
  --md-sys-color-surface-container-highest: #303633;
}
```

### 1.4 Semantic Colour Aliases

```css
:root {
  /* Theme badge colours */
  --color-theme-account:   #006B4B; /* AAL, OBV */
  --color-theme-transact:  #3E6374; /* TDW, TIC */
  --color-theme-technical: #B85C00; /* APR */
  --color-theme-support:   #7A1A8E; /* CSR */
  --color-theme-business:  #8B5000; /* FPC */
  --color-theme-compliance:#005FAF; /* TSD */

  /* Sentiment dot colours */
  --color-rating-1: #BA1A1A;
  --color-rating-2: #D4690A;
  --color-rating-3: #857400;
  --color-rating-4: #3C6A00;
  --color-rating-5: #006B4B;
}
```

---

## 2. Typography (M3 Type Scale)

```css
:root {
  /* Display */
  --md-sys-typescale-display-large:   3.5625rem/1.12  'DM Serif Display', serif;
  --md-sys-typescale-display-medium:  2.8125rem/1.16  'DM Serif Display', serif;
  --md-sys-typescale-display-small:   2.25rem/1.22    'DM Serif Display', serif;

  /* Headline */
  --md-sys-typescale-headline-large:  2rem/1.25       'Inter', sans-serif;
  --md-sys-typescale-headline-medium: 1.75rem/1.29    'Inter', sans-serif;
  --md-sys-typescale-headline-small:  1.5rem/1.33     'Inter', sans-serif;

  /* Title */
  --md-sys-typescale-title-large:     1.375rem/1.27   'Inter', sans-serif; /* 600 */
  --md-sys-typescale-title-medium:    1rem/1.5        'Inter', sans-serif; /* 500 */
  --md-sys-typescale-title-small:     0.875rem/1.43   'Inter', sans-serif; /* 500 */

  /* Body */
  --md-sys-typescale-body-large:      1rem/1.5        'Inter', sans-serif; /* 400 */
  --md-sys-typescale-body-medium:     0.875rem/1.43   'Inter', sans-serif; /* 400 */
  --md-sys-typescale-body-small:      0.75rem/1.33    'Inter', sans-serif; /* 400 */

  /* Label */
  --md-sys-typescale-label-large:     0.875rem/1.43   'Inter', sans-serif; /* 500 */
  --md-sys-typescale-label-medium:    0.75rem/1.33    'Inter', sans-serif; /* 500 */
  --md-sys-typescale-label-small:     0.6875rem/1.45  'Inter', sans-serif; /* 500 */
}
```

### Typography Usage Map

| Token | Used for |
|---|---|
| `display-large` | Hero headline on the landing page only |
| `headline-medium` | Page section titles (Themes, Quotes, Actions) |
| `headline-small` | Card titles |
| `title-large` | Theme name labels |
| `title-medium` | Card metadata labels |
| `body-large` | Review quote body text |
| `body-medium` | Action idea body text |
| `label-large` | Buttons, chips |
| `label-medium` | Badges, status pills |
| `label-small` | Timestamps, word counts, footnotes |

---

## 3. Elevation & Surfaces (M3 Tonal Elevation)

M3 expresses elevation as surface tint intensity, not shadow depth.

```css
:root {
  --md-sys-elevation-0: var(--md-sys-color-surface-container-lowest);  /* flat */
  --md-sys-elevation-1: var(--md-sys-color-surface-container-low);     /* card resting */
  --md-sys-elevation-2: var(--md-sys-color-surface-container);         /* card hover */
  --md-sys-elevation-3: var(--md-sys-color-surface-container-high);    /* modal backdrop */
  --md-sys-elevation-4: var(--md-sys-color-surface-container-highest); /* nav bar */
}
```

Shadow is used sparingly — only for modals and floating action elements:

```css
--shadow-1: 0 1px 2px rgba(0,0,0,.08);
--shadow-2: 0 2px 6px rgba(0,0,0,.10);
--shadow-3: 0 4px 12px rgba(0,0,0,.12);
```

---

## 4. Shape System (M3 Corner Radius)

```css
:root {
  --md-sys-shape-corner-none:        0px;
  --md-sys-shape-corner-extra-small: 4px;
  --md-sys-shape-corner-small:       8px;
  --md-sys-shape-corner-medium:      12px;
  --md-sys-shape-corner-large:       16px;
  --md-sys-shape-corner-extra-large: 28px;
  --md-sys-shape-corner-full:        9999px;
}
```

| Component | Shape token |
|---|---|
| Buttons | `corner-full` |
| Chips / badges | `corner-full` |
| Cards | `corner-large` |
| Input fields | `corner-extra-large` |
| Modals / dialogs | `corner-extra-large` |
| Snackbars | `corner-small` |
| Progress steps | `corner-medium` |

---

## 5. Motion System (Framer Motion + M3 Easing)

### 5.1 M3 Easing Curves

```css
:root {
  --md-sys-motion-easing-standard:          cubic-bezier(0.2, 0, 0, 1.0);
  --md-sys-motion-easing-standard-decel:    cubic-bezier(0, 0, 0, 1.0);
  --md-sys-motion-easing-standard-accel:    cubic-bezier(0.3, 0, 1, 1);
  --md-sys-motion-easing-emphasized:        cubic-bezier(0.2, 0, 0, 1.0);
  --md-sys-motion-easing-emphasized-decel:  cubic-bezier(0.05, 0.7, 0.1, 1.0);
  --md-sys-motion-easing-emphasized-accel:  cubic-bezier(0.3, 0, 0.8, 0.15);
}
```

### 5.2 Duration Tokens

```css
:root {
  --md-sys-motion-duration-short1:  50ms;
  --md-sys-motion-duration-short2:  100ms;
  --md-sys-motion-duration-short3:  150ms;
  --md-sys-motion-duration-short4:  200ms;
  --md-sys-motion-duration-medium1: 250ms;
  --md-sys-motion-duration-medium2: 300ms;
  --md-sys-motion-duration-medium3: 350ms;
  --md-sys-motion-duration-medium4: 400ms;
  --md-sys-motion-duration-long1:   450ms;
  --md-sys-motion-duration-long2:   500ms;
  --md-sys-motion-duration-long3:   550ms;
  --md-sys-motion-duration-long4:   600ms;
}
```

### 5.3 Framer Motion Variants (shared)

```ts
// src/motion/variants.ts

export const fadeUp = {
  hidden:  { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0,  transition: { duration: 0.4, ease: [0.05, 0.7, 0.1, 1.0] } },
  exit:    { opacity: 0, y: -8, transition: { duration: 0.2, ease: [0.3, 0, 0.8, 0.15] } },
};

export const staggerChildren = {
  visible: { transition: { staggerChildren: 0.07 } },
};

export const scaleIn = {
  hidden:  { opacity: 0, scale: 0.94 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.35, ease: [0.05, 0.7, 0.1, 1.0] } },
};

export const slideInRight = {
  hidden:  { opacity: 0, x: 32 },
  visible: { opacity: 1, x: 0,  transition: { duration: 0.45, ease: [0.05, 0.7, 0.1, 1.0] } },
  exit:    { opacity: 0, x: -24, transition: { duration: 0.2, ease: [0.3, 0, 0.8, 0.15] } },
};

export const pipelineStep = {
  idle:    { scale: 1, opacity: 0.5 },
  active:  { scale: 1.02, opacity: 1,  transition: { duration: 0.3, ease: [0.05, 0.7, 0.1, 1.0] } },
  done:    { scale: 1, opacity: 1,     transition: { duration: 0.2 } },
};
```

### 5.4 Motion Rules

| Trigger | Approach |
|---|---|
| Page enter | `fadeUp` on container, `staggerChildren` on cards |
| Card hover | `scale(1.015)` + `shadow-2`, `duration-short4` |
| Pipeline step activate | `pipelineStep.active` — subtle lift |
| Pipeline step complete | Checkmark icon swaps in via `scaleIn`; green tint fades in |
| Quote reveal | `slideInRight` per quote, staggered 80ms |
| Modal open | `scaleIn` on panel + backdrop fade-in |
| Snackbar | Slide up from bottom-right, auto-dismiss after 4s |
| Theme toggle | Colour tokens crossfade via CSS transition `300ms standard` |

---

## 6. Component Library

### 6.1 `<PipelineTracker />`

Displays the 8-step pipeline as a horizontal step rail at the top of the Run page. Each step shows an icon, label, and one of four states: `idle`, `active`, `done`, `error`.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ① Ingest  ──  ② Redact  ──  ③ Classify  ──  ④ Select  ──  ⑤ Quotes  ──  … │
│  ✓ done       ✓ done        ● active         ○ idle        ○ idle            │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Active step pulses with a `primary-container` glow ring (Framer `animate` loop, `duration-long4`, 0.6 opacity → 1.0)
- Connector line fills left-to-right using a CSS `scaleX` transition as steps complete
- On mobile: collapses to a vertical stepper in a bottom sheet

**Props:**
```ts
type Step = {
  id: number;
  label: string;
  icon: string;           // Material Symbol name
  state: 'idle' | 'active' | 'done' | 'error';
  detail?: string;        // e.g. "127 reviews loaded"
};
```

---

### 6.2 `<ThemeCard />`

Used in the Top Themes section of the Results page. One card per top theme.

```
┌─────────────────────────────────────────────────┐
│  ● APR                               #1 / 47 reviews │
│  App performance, bugs & reliability              │
│                                                   │
│  Crashes, slow loads, UI errors                   │
│                                                   │
│  ★★☆☆☆  avg 2.1                                  │
└─────────────────────────────────────────────────┘
```

- Left border `4px` uses the theme category colour (`--color-theme-technical`)
- Badge pill (top-left) shows the short code (`APR`) in `label-medium`
- Review count chip (top-right) in `surface-container-high`
- Hover: `scale(1.015)` + `elevation-2`
- Rank `#1` has a subtle `primary-container` tint on the background

**Props:**
```ts
type ThemeCardProps = {
  rank: number;
  theme: string;
  shortCode: string;
  category: 'account' | 'transact' | 'technical' | 'support' | 'business' | 'compliance';
  reviewCount: number;
  avgRating: number;
  description: string;
};
```

---

### 6.3 `<QuoteBlock />`

Used in the Real User Quotes section. One per theme.

```
┌──────────────────────────────────────────────────────────────────┐
│  "                                                               │
│   Every time I open the app I have to log back in. Very         │
│   annoying.                                                      │
│  "                                                               │
│                                  — App Store · ★★☆☆☆ · Mar 2026 │
└──────────────────────────────────────────────────────────────────┘
```

- Large typographic opening quote mark (`DM Serif Display`, `display-small`, `primary` colour, `0.15` opacity)
- Quote body in `body-large`, `on-surface`
- Attribution in `label-medium`, `on-surface-variant`, right-aligned
- Platform badge (App Store / Google Play) as an icon + text chip
- Enters via `slideInRight`, staggered 80ms per quote
- On hover: left border `2px primary` appears via `opacity` transition

**Props:**
```ts
type QuoteBlockProps = {
  quote: string;
  platform: 'App Store' | 'Google Play';
  rating: number;
  date: string;         // "Mar 2026"
  linkedTheme: string;
};
```

---

### 6.4 `<ActionCard />`

Used in the Action Ideas section. One per action idea.

```
┌──────────────────────────────────────────────────────────────────┐
│  01                  Account access & login                      │
│  ──────────────────────────────────────────                      │
│  Investigate persistent session expiry on iOS — check token      │
│  refresh timing and background app state handling.               │
└──────────────────────────────────────────────────────────────────┘
```

- Large monospaced number (`display-small`, `primary-container` background, `on-primary-container` text, `corner-medium`, top-left)
- Theme tag in `label-medium` chip, top-right
- Action body in `body-large`
- On hover: number block transitions to `primary` background

**Props:**
```ts
type ActionCardProps = {
  index: number;
  action: string;
  linkedTheme: string;
};
```

---

### 6.5 `<PulseNoteBanner />`

The assembled weekly note rendered as a scannable one-page banner at the top of the Results page. Uses print-optimised styling so it looks identical when printed or exported to PDF.

```
┌───────────────────────────────────────────────────────────────────────┐
│  Wealthsimple Canada — Weekly Review Pulse                            │
│  Period: 2026-03-15 to 2026-06-07 · 127 reviews                      │
│                                                                       │
│  TOP THEMES          REAL USER QUOTES         ACTION IDEAS            │
│  1. App perf…        "Every time I open…"     1. Investigate…         │
│  2. Account…         "Transfer stuck for…"    2. Add status…          │
│  3. Customer…        "Support took 5 days…"   3. Surface in-app…      │
│                                                                       │
│                              219 words · Generated 2026-06-07         │
└───────────────────────────────────────────────────────────────────────┘
```

- Three-column layout on desktop (≥ 1024px); single column on mobile
- Background: `surface-container-low`; border: `1px outline-variant`; `corner-extra-large`
- "Copy note" FAB (floating action button) — bottom-right; copies note markdown to clipboard
- "Export PDF" secondary button — triggers `window.print()` with a print-specific stylesheet

---

### 6.6 `<EmailPreview />`

A simulated email client panel rendered below the pulse note. Shows the email draft in a mock inbox envelope.

```
┌──────────────────────────────────────────────────────────────┐
│  ✉  Email Draft                               [Copy] [Edit]  │
│  ─────────────────────────────────────────────────────────── │
│  To:      mohdammar97@gmail.com                              │
│  Subject: Weekly Review Pulse — Wealthsimple Canada          │
│  ─────────────────────────────────────────────────────────── │
│  Hi Team,                                                    │
│                                                              │
│  Here is this week's review pulse for Wealthsimple Canada.   │
│                                                              │
│  [pulse note content here]                                   │
│                                                              │
│  Thanks,                                                     │
│  [Your Name]                                                 │
└──────────────────────────────────────────────────────────────┘
```

- Monospace font for the `To:` / `Subject:` header section
- Inline edit mode on `[Edit]` click — replaces `sender_name` placeholder with a text input
- `[Copy]` writes `email_draft.txt` content to clipboard; shows a Snackbar confirmation

---

### 6.7 `<UploadZone />`

The CSV drop zone on the Upload / Run page.

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│          ↑  Drop reviews.csv here                      │
│             or click to browse                         │
│                                                        │
│   Required: platform, rating, title, text, date        │
│   Optional: app_version, country, helpful_votes        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

- Dashed `2px outline-variant` border; `corner-extra-large`
- On drag-over: border transitions to `primary`, background to `primary-container` at `0.08` opacity
- File validation on drop: checks extension (`.csv`) and presence of required headers; shows inline error if invalid
- On valid file: shows filename chip + row count estimate + "Run pipeline" CTA button

---

### 6.8 `<RunSummaryChip />`

Small status pill shown in the page header after a run.

```
  ✓  127 reviews · 5 themes · 218 words · 2026-06-07 10:04 UTC
```

- `label-medium`, `secondary-container` background
- Green checkmark icon from Material Symbols
- Warning variant: amber background for `low_data_warning: true`

---

### 6.9 `<ThemeLegendDrawer />`

A right-side drawer listing all eight themes with short codes and descriptions. Triggered by a "Theme legend" icon button in the top-right of the Results page.

- Opens with a `slideInRight` animation, `duration-long2`
- Backdrop dims the main content at `0.32` opacity
- Each theme row shows: colour dot, short code chip, label, description
- Close via `×` button or `Escape` key or backdrop click

---

### 6.10 `<RatingBar />`

A compact horizontal bar chart showing rating distribution for a theme.

```
★★★★★  ████░░░░░░  42%
★★★★☆  ██░░░░░░░░  18%
★★★☆☆  █░░░░░░░░░   8%
★★☆☆☆  ████████░░  24%
★☆☆☆☆  ██░░░░░░░░   8%
```

- Each bar is `height: 6px`, `corner-full`, filled with the semantic rating colour
- Animates width from `0` to final value on mount, `duration-long2`, `emphasized-decel`

---

## 7. Page & View Specifications

### 7.1 Route Map

```
/                   → Landing page (product overview + upload CTA)
/run                → Upload CSV + pipeline tracker + live step progress
/results            → Pulse note + themes + quotes + actions + email
/results/note       → Printable one-page note view
/results/email      → Email draft standalone view
```

### 7.2 Landing Page (`/`)

**Layout:** Centred, single column, max-width 720px

```
┌──────────────────────────────────────────────────┐
│                                                  │
│   Weekly Review Pulse          [Theme]           │
│   for Wealthsimple Canada                        │
│                                                  │
│   Turn 8–12 weeks of app reviews into a          │
│   250-word product insight note. Every week.     │
│                                                  │
│   [  Upload reviews.csv  →  Run pipeline  ]      │
│                                                  │
│   ───────────────────────────────────────        │
│   ① Import  ② Redact  ③ Classify  ④ Select      │
│   ⑤ Quotes  ⑥ Actions  ⑦ Note  ⑧ Email          │
│   ───────────────────────────────────────        │
│                                                  │
│   Designed for Product · Support · Leadership    │
│                                                  │
└──────────────────────────────────────────────────┘
```

- Hero headline in `display-small`, `DM Serif Display`
- Subtitle in `body-large`, `on-surface-variant`
- CTA: filled M3 button → navigates to `/run`
- Pipeline mini-diagram: icon row with `label-small` labels, `surface-container-low` background strip

### 7.3 Run Page (`/run`)

**Layout:** Two-panel — left: upload zone; right: pipeline tracker (collapses to top/bottom stack on mobile)

```
┌────────────────────┬──────────────────────────────────────────┐
│                    │  ① Ingest   ✓  127 reviews loaded        │
│  DROP CSV HERE     │  ② Redact   ✓  4 rows flagged PII        │
│                    │  ③ Classify ●  Classifying batch 2/3…    │
│  reviews.csv       │  ④ Select   ○                            │
│  142 rows          │  ⑤ Quotes   ○                            │
│                    │  ⑥ Actions  ○                            │
│  [Run Pipeline]    │  ⑦ Note     ○                            │
│                    │  ⑧ Email    ○                            │
│                    │                                          │
│                    │  [  View Results  ]  (disabled til done) │
└────────────────────┴──────────────────────────────────────────┘
```

- Each step row animates from `idle` → `active` (pulsing ring) → `done` (checkmark + detail text) → `error` (red × + error message)
- Spinner on active step: Framer `animate={{ rotate: 360 }}`, `repeat: Infinity`, `ease: "linear"`, `duration: 1`
- "View Results" CTA button slides up from below with `fadeUp` when all steps are `done`
- On error: an M3 error container card slides in below the failed step with the error message and a "Retry" button

### 7.4 Results Page (`/results`)

**Layout:** Single column, max-width 960px, centred, section-separated

```
┌─────────────────────────────────────────────────────────┐
│  ← Back to Run          [Theme Legend]   [Export PDF]   │
│                                                         │
│  Run summary chip: ✓ 127 reviews · 5 themes · 218 words │
│                                                         │
│  ┌─── Pulse Note Banner (full width) ──────────────┐    │
│  │  [Three-column: themes | quotes | actions]       │    │
│  └──────────────────────────────────────────────────┘    │
│                                                         │
│  ── Top Themes ──────────────────────────────────────   │
│  [ThemeCard #1] [ThemeCard #2] [ThemeCard #3]           │
│                                                         │
│  ── Real User Quotes ────────────────────────────────   │
│  [QuoteBlock 1]                                         │
│  [QuoteBlock 2]                                         │
│  [QuoteBlock 3]                                         │
│                                                         │
│  ── Action Ideas ────────────────────────────────────   │
│  [ActionCard 1] [ActionCard 2] [ActionCard 3]           │
│                                                         │
│  ── Email Draft ─────────────────────────────────────   │
│  [EmailPreview]                                         │
└─────────────────────────────────────────────────────────┘
```

- Section headers use `headline-medium`, `on-surface`, with a `1px outline-variant` rule beneath
- Each section enters via `staggerChildren` + `fadeUp` as the user scrolls into view (Framer `whileInView`)
- Sticky top bar: shows run summary chip and action buttons (stays in view during scroll)

### 7.5 Printable Note View (`/results/note`)

- Stripped UI: no navigation, no interactive elements
- White background (`surface-container-lowest`), `on-surface` text
- Print stylesheet removes all shadows, reduces border to `1px solid #ccc`
- Auto-triggered by "Export PDF" button via `window.print()`
- Footer prints: `Generated: {timestamp} · Wealthsimple Canada · Weekly Review Pulse`

---

## 8. Layout Grid

### Desktop (≥ 1280px)
- 12-column grid, `24px` gutter, `80px` margin
- Content max-width: `960px`

### Tablet (768px – 1279px)
- 8-column grid, `16px` gutter, `32px` margin

### Mobile (< 768px)
- 4-column grid, `16px` gutter, `16px` margin
- `ThemeCard` stack vertically
- `ActionCard` stack vertically
- `PipelineTracker` becomes a vertical stepper

---

## 9. Spacing Scale

Based on a `4px` base unit:

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
}
```

---

## 10. Accessibility

| Requirement | Implementation |
|---|---|
| Colour contrast | All text on surface meets WCAG AA (4.5:1 for body, 3:1 for large) |
| Focus visible | M3 focus ring: `3px solid primary`, `2px offset` |
| Screen reader | `aria-live="polite"` on pipeline step updates |
| Keyboard navigation | All interactive elements reachable via Tab; drawer closable via Escape |
| Reduced motion | `@media (prefers-reduced-motion)` disables all Framer Motion animations; elements appear instantly |
| Semantic HTML | `<main>`, `<section>`, `<article>`, `<blockquote>` for quote blocks |
| ARIA labels | Icon-only buttons have `aria-label`; rating bars have `aria-valuenow` |

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 11. Theme Toggle

- Persisted in `localStorage` as `"light"` | `"dark"`
- Defaults to OS preference via `prefers-color-scheme`
- Toggle button in top-right nav: Material Symbol `light_mode` / `dark_mode`
- Colour token crossfade: `transition: background-color 300ms, color 300ms` on `:root`

---

## 12. Project File Structure (Frontend)

```
src/
│
├── app/
│   ├── layout.tsx              # Root layout, theme provider, font imports
│   ├── page.tsx                # Landing page (/)
│   ├── run/
│   │   └── page.tsx            # Run page (/run)
│   └── results/
│       ├── page.tsx            # Results page (/results)
│       ├── note/
│       │   └── page.tsx        # Printable note (/results/note)
│       └── email/
│           └── page.tsx        # Email draft view (/results/email)
│
├── components/
│   ├── PipelineTracker/
│   │   ├── PipelineTracker.tsx
│   │   └── PipelineTracker.module.css
│   ├── ThemeCard/
│   │   ├── ThemeCard.tsx
│   │   └── ThemeCard.module.css
│   ├── QuoteBlock/
│   │   ├── QuoteBlock.tsx
│   │   └── QuoteBlock.module.css
│   ├── ActionCard/
│   │   ├── ActionCard.tsx
│   │   └── ActionCard.module.css
│   ├── PulseNoteBanner/
│   │   ├── PulseNoteBanner.tsx
│   │   └── PulseNoteBanner.module.css
│   ├── EmailPreview/
│   │   ├── EmailPreview.tsx
│   │   └── EmailPreview.module.css
│   ├── UploadZone/
│   │   ├── UploadZone.tsx
│   │   └── UploadZone.module.css
│   ├── RatingBar/
│   │   ├── RatingBar.tsx
│   │   └── RatingBar.module.css
│   └── ThemeLegendDrawer/
│       ├── ThemeLegendDrawer.tsx
│       └── ThemeLegendDrawer.module.css
│
├── motion/
│   └── variants.ts             # Shared Framer Motion variants
│
├── styles/
│   ├── tokens.css              # All CSS custom properties (colours, type, shape, space)
│   ├── global.css              # Reset, base element styles
│   └── print.css               # Print-specific overrides
│
├── hooks/
│   ├── usePipelineStatus.ts    # Polls /api/pipeline/status SSE stream
│   ├── useTheme.ts             # Dark/light toggle with localStorage
│   └── useClipboard.ts         # Copy-to-clipboard with toast feedback
│
└── types/
    └── pipeline.ts             # TypeScript types matching data_model.md schemas
```

---

## 13. API Integration Points

The Next.js frontend communicates with the Python MCP pipeline via a thin API layer.

| Route | Method | Purpose |
|---|---|---|
| `/api/upload` | `POST` | Accepts `multipart/form-data` with `reviews.csv`; saves to `data/input/` |
| `/api/run` | `POST` | Triggers `python main.py`; returns `run_id` |
| `/api/pipeline/status` | `GET` (SSE) | Server-sent events; emits step state updates in real time |
| `/api/results` | `GET` | Returns `run_summary.json` + parsed `weekly_note.md` + `email_draft.txt` |
| `/api/results/csv` | `GET` | Streams `data/output/reviews_clean.csv` for download |

```ts
// src/types/pipeline.ts

export type StepState = 'idle' | 'active' | 'done' | 'error';

export type PipelineStatus = {
  steps: Array<{
    id: number;
    label: string;
    state: StepState;
    detail?: string;
  }>;
  completed: boolean;
  error?: string;
};

export type RunResult = {
  runId: string;
  periodStart: string;
  periodEnd: string;
  reviewCount: number;
  themes: ThemeSummary[];
  quotes: QuoteRecord[];
  actions: ActionRecord[];
  noteText: string;
  wordCount: number;
  emailText: string;
  lowDataWarning: boolean;
};
```

---

## 14. Key Design Decisions

| Decision | Rationale |
|---|---|
| No charting library | The output is a _reading surface_; bar charts and pie charts would shift focus away from the words |
| `DM Serif Display` for headlines | Adds editorial warmth to a data-heavy product; contrasts cleanly with `Inter` |
| `body-large` for quote text | Quotes are the primary evidence — they deserve generous line-height and size |
| Colour-coded themes | Eight themes map to six semantic categories; colour coding lets the eye find patterns instantly |
| SSE for pipeline progress | Real-time step updates without polling; no WebSocket overhead for a short-lived pipeline run |
| CSS Modules (not Tailwind) | Keeps styling co-located with components; avoids utility-class sprawl in a design-system project |
| Print stylesheet for PDF export | No server-side PDF generation needed; browser print produces reliable one-page output |
| M3 tonal elevation over box shadows | Cleaner light/dark switching; consistent with the design system; avoids visual weight |
