import { api } from './api';
import { pad } from './format';
import { Logo } from './Staff';
import { usePoll } from './usePoll';

/** Waiting-room TV screen: the numbers being served and how many are waiting. */
export default function Display({ slug }: { slug: string }) {
  const { data: q, error } = usePoll(() => api.publicQueue(slug), 3000);
  return (
    <main className="display">
      <header className="row between">
        <div className="brand"><Logo /> {q?.name ?? 'QueueFlow'}</div>
        <div className="muted">{q ? `${q.waiting} waiting` : ''}</div>
      </header>
      {error && <p className="error">{error}. Retrying…</p>}
      <h1 className="display-h">Now serving</h1>
      <div className="display-grid" aria-live="polite">
        {q?.now_serving.length === 0 && <p className="muted">Please wait to be called.</p>}
        {q?.now_serving.map((s) => (
          <div key={s.number} className="card display-card">
            <div className="display-num">{pad(s.number)}</div>
            <div className="display-counter">{s.counter}</div>
          </div>
        ))}
      </div>
      <p className="muted display-foot">Join from your phone: {window.location.origin}{window.location.pathname}#/q/{slug}</p>
    </main>
  );
}
