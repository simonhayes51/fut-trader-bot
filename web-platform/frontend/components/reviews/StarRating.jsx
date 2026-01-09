export default function StarRating({ rating, size = 'md', showNumber = false }) {
  const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-2xl',
    xl: 'text-4xl'
  };

  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;

  return (
    <div className="flex items-center space-x-1">
      <div className={`flex items-center ${sizeClasses[size]}`}>
        {[...Array(5)].map((_, index) => {
          if (index < fullStars) {
            return <span key={index}>⭐</span>;
          } else if (index === fullStars && hasHalfStar) {
            return <span key={index}>⭐</span>; // Could use half-star icon
          } else {
            return <span key={index} className="text-gray-300">☆</span>;
          }
        })}
      </div>
      {showNumber && (
        <span className="text-gray-600 font-medium ml-1">
          {rating.toFixed(1)}
        </span>
      )}
    </div>
  );
}
