import { cn } from '../../utils/cn';

const BANDS = [
  { min: 85, label: 'Excellent', variant: 'text-success', stroke: 'stroke-success' },
  { min: 70, label: 'Good', variant: 'text-accent', stroke: 'stroke-accent' },
  { min: 50, label: 'Needs work', variant: 'text-warning', stroke: 'stroke-warning' },
  { min: 0, label: 'Weak', variant: 'text-danger', stroke: 'stroke-danger' },
];

export const scoreBand = (score) => BANDS.find((band) => score >= band.min) || BANDS[BANDS.length - 1];

/** Circular SEO score gauge (0-100) with its qualitative band. */
export function ScoreGauge({ score = 0, size = 104, label = 'SEO score' }) {
  const safeScore = Math.max(0, Math.min(100, Number(score) || 0));
  const band = scoreBand(safeScore);
  const radius = size / 2 - 8;
  const circumference = 2 * Math.PI * radius;
  const dash = (safeScore / 100) * circumference;

  return (
    <div className="flex items-center gap-3">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${label}: ${safeScore} out of 100`}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth="7"
          className="stroke-border"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className={cn('transition-all duration-500', band.stroke)}
        />
        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          dominantBaseline="middle"
          className="fill-current text-[22px] font-semibold"
        >
          {safeScore}
        </text>
        <text
          x="50%"
          y="65%"
          textAnchor="middle"
          dominantBaseline="middle"
          className="fill-current text-[10px] uppercase tracking-wide opacity-60"
        >
          / 100
        </text>
      </svg>
      <div>
        <p className={cn('text-sm font-semibold', band.variant)}>{band.label}</p>
        <p className="text-xs text-muted">
          Self-assessed by the model. Edit the metadata and the score is recalculated on
          regeneration, not on typing.
        </p>
      </div>
    </div>
  );
}

export default ScoreGauge;
