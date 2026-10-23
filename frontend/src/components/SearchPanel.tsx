interface SearchPanelProps {
  product: string;
  running: boolean;
  starting: boolean;
  status: string;
  onProduct: (value: string) => void;
  onStart: () => void;
  onStop: () => void;
}

export function SearchPanel({
  product,
  running,
  starting,
  status,
  onProduct,
  onStart,
  onStop,
}: SearchPanelProps) {
  return (
    <section className="search-block">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!running && !starting && product.trim().length >= 2) {
            onStart();
          }
        }}
      >
        <label className="section-kicker" htmlFor="product">
          Product search
        </label>
        <div className="search-row">
          <input
            id="product"
            type="text"
            value={product}
            placeholder="e.g., Redmi 15C 5G 128 GB, 6 GB RAM, Mobile Phone"
            onChange={(event) => onProduct(event.target.value)}
          />
          <button type="submit" disabled={running || starting || product.trim().length < 2}>
            Start Search
          </button>
          <button type="button" className="stop" onClick={onStop} disabled={!running}>
            Stop Search
          </button>
        </div>
        <p className="search-status" role="status">
          <span className="status-dot" aria-hidden="true" />
          {status}
        </p>
        <p className="tip">
          Tip: Be as specific as possible. Include brand, model, storage, or variant.
        </p>
      </form>
    </section>
  );
}
