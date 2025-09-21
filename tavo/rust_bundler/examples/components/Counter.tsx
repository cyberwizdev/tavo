import React, { useState } from 'react';

export default function Counter() {
  const [count, setCount] = useState(0);

  const increment = () => setCount(count + 1);
  const decrement = () => setCount(count - 1);

  return (
    <div className="counter">
      <h3>Interactive Counter</h3>
      <div className="counter-controls">
        <button onClick={decrement} className="btn btn-secondary">
          -
        </button>
        <span className="count-display">{count}</span>
        <button onClick={increment} className="btn btn-primary">
          +
        </button>
      </div>
      <p className="counter-description">
        This counter demonstrates client-side hydration. 
        The initial render happens on the server, then becomes interactive in the browser.
      </p>
    </div>
  );
}