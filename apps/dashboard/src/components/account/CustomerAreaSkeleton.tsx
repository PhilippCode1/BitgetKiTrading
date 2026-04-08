export function CustomerAreaSkeleton() {
  return (
    <div className="customer-area-skeleton" aria-busy="true" aria-live="polite">
      <div className="customer-area-skeleton__header">
        <div className="customer-area-skeleton__line customer-area-skeleton__line--title" />
        <div className="customer-area-skeleton__line customer-area-skeleton__line--sub" />
      </div>
      <div className="customer-area-skeleton__grid">
        <div className="customer-area-skeleton__card" />
        <div className="customer-area-skeleton__card" />
        <div className="customer-area-skeleton__card" />
      </div>
      <div className="customer-area-skeleton__panel">
        <div className="customer-area-skeleton__line" />
        <div className="customer-area-skeleton__line" />
        <div className="customer-area-skeleton__line customer-area-skeleton__line--short" />
      </div>
    </div>
  );
}
