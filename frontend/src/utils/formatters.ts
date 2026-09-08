export const formatDate = (dateString: string) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

export const formatScore = (score: number | undefined | null) => {
  if (score === undefined || score === null) return '-';
  return score.toFixed(1);
};

export const formatPercent = (percent: number | undefined | null) => {
  if (percent === undefined || percent === null) return '0%';
  return `${percent.toFixed(1)}%`;
};
