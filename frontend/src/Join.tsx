import { FormEvent, useState } from 'react';
import { api, ApiError } from './api';
import { waitText } from './format';
import { Logo } from './Staff';
import { usePoll } from './usePoll';

export default function Join({ slug }: { slug: string }) {
  const { data: queue, error } = usePoll(() => api.publicQueue(slug), 5000);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setProblem('');
    try {
      const t = await api.join(slug, name);
      window.location.hash = `#/t/${t.token}`;
    } catch (err) {
      setProblem(err instanceof ApiError ? err.message : 'Could not reach the server');
      setBusy(false);
    }
  }

  return (
    <main className="phone">
      <div className="brand"><Logo /> QueueFlow</div>
      {error && !queue && <p className="error" role="alert">{error}</p>}
      {queue && (
        <form className="card stack" onSubmit={submit}>
          <h1>{queue.name}</h1>
          {queue.is_open ? (
            <p className="muted">
              {queue.waiting === 0 ? 'Nobody is waiting. ' : `${queue.waiting} ${queue.waiting === 1 ? 'person is' : 'people are'} ahead, `}
              {queue.waiting > 0 && <>expected wait {waitText(queue.estimated_wait_minutes)}.</>}
            </p>
          ) : (
            <p className="error">This queue is closed right now.</p>
          )}
          <label>
            Your first name
            <input required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} autoComplete="given-name" placeholder="e.g. Malee" />
          </label>
          {problem && <p className="error" role="alert">{problem}</p>}
          <button className="primary big" disabled={busy || !queue.is_open}>{busy ? 'Joining…' : 'Join the queue'}</button>
          <p className="muted small">Keep this page open. It shows your place in line and tells you when it's your turn.</p>
        </form>
      )}
    </main>
  );
}
