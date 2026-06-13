export type StepState = 'idle' | 'active' | 'done' | 'error';

export type PipelineStep = {
  id: number;
  label: string;
  icon: string;
  state: StepState;
  detail?: string;
};

export type PipelineStatus = {
  steps: PipelineStep[];
  completed: boolean;
  error?: string;
};

export type ThemeSummary = {
  theme: string;
  reviewCount: number;
  avgRating: number;
  rank: number;
};

export type QuoteRecord = {
  theme: string;
  quote: string;
  reviewId: number;
  verified: boolean;
  platform?: string;
  rating?: number;
  date?: string;
};

export type ActionRecord = {
  action: string;
  linkedTheme: string;
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
  generatedAt?: string;
};

export type UploadState =
  | { status: 'idle' }
  | { status: 'validating' }
  | { status: 'valid'; filename: string; rowCount: number }
  | { status: 'invalid'; error: string }
  | { status: 'uploading' }
  | { status: 'running'; runId: string };

export const THEME_CODES: Record<string, string> = {
  'Account access & login':             'AAL',
  'Onboarding & verification':          'OBV',
  'Transfers, deposits & withdrawals':  'TDW',
  'Trading, investing & crypto':        'TIC',
  'App performance, bugs & reliability':'APR',
  'Customer support & issue resolution':'CSR',
  'Fees, pricing & product communication': 'FPC',
  'Tax, statements & documents':        'TSD',
};

export type ThemeCategory = 'account' | 'transact' | 'technical' | 'support' | 'business' | 'compliance';

export const THEME_CATEGORIES: Record<string, ThemeCategory> = {
  'Account access & login':             'account',
  'Onboarding & verification':          'account',
  'Transfers, deposits & withdrawals':  'transact',
  'Trading, investing & crypto':        'transact',
  'App performance, bugs & reliability':'technical',
  'Customer support & issue resolution':'support',
  'Fees, pricing & product communication': 'business',
  'Tax, statements & documents':        'compliance',
};
