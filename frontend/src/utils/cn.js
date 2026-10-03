/** Tiny class-name helper (keeps conditional Tailwind classes readable). */
export function cn(...values) {
  return values
    .flat()
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
}
