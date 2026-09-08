export const getSentimentColor = (sentiment: string | undefined) => {
  switch (sentiment?.toLowerCase()) {
    case 'positive':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'negative':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'neutral':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
};

export const getScoreColor = (score: number | undefined) => {
  if (score === undefined) return 'text-gray-500';
  if (score >= 4.0) return 'text-green-600';
  if (score >= 2.5) return 'text-yellow-600';
  return 'text-red-600';
};
