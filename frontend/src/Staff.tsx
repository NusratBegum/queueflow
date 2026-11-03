import { FormEvent, useEffect, useState } from 'react';
import { api, ApiError, Board, isLoggedIn, login, logout, Queue, Ticket } from './api';
import { clock, minutesSince, pad } from './format';
import { usePoll } from './usePoll';

const COUNTERS = ['Counter 1', 'Counter 2'];

export default function Staff() {
  const [signedIn, setSignedIn] = useState(isLoggedIn());
  const [queue, setQueue] = useState<Queue | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    api.queues().then((qs) => setQueue(qs[0] ?? null)).catch(() => setSignedIn(isLoggedIn()));
  }, [signedIn]);

  if (!signedIn) return <Login onDone={() => setSignedIn(true)} />;
  if (!queue) return <main className="center muted">Loading your queue…</main>;
  return <BoardView queue={queue} onSignOut={() => { logout(); setSignedIn(false); }} />;
}

function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState('demo@queueflow.dev');
  const [password, setPassword] = useState('demo-queue-2026');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="center">
      <form className="card login" onSubmit={submit}>
        <div className="brand"><Logo /> QueueFlow</div>
        <p className="muted">
          Walk-in queues for clinics and shops. Customers join from their phone and see their place in line; staff call the
          next person. This demo is a dental clinic's front desk.
        </p>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in to the front desk'}</button>
        <p className="muted small">The demo account is filled in for you.</p>
      </form>
    </main>
  );
}

function BoardView({ queue, onSignOut }: { queue: Queue; onSignOut: () => void }) {
  const { data: board, error, refresh } = usePoll<Board>(() => api.board(queue.id), 3000);
  const [counter, setCounter] = useState(COUNTERS[0]);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  async function act(fn: () => Promise<unknown>, ok?: string) {
    setBusy(true);
    setNotice('');
    try {
      await fn();
      if (ok) setNotice(ok);
      await refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  }

  const joinUrl = `${window.location.origin}${window.location.pathname}#/q/${queue.slug}`;
  const displayUrl = `${window.location.origin}${window.location.pathname}#/display/${queue.slug}`;
  const isOpen = board?.queue.is_open ?? queue.is_open;
  const mine = board?.now_serving.filter((t) => t.counter === counter) ?? [];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><Logo /> QueueFlow <span className="muted subtle">{queue.name}</span></div>
        <div className="row">
          <span className={`pill ${isOpen ? 'pill-good' : 'pill-bad'}`}>{isOpen ? 'Open' : 'Closed'}</span>
          <button onClick={() => act(() => api.setOpen(queue.id, !isOpen))} disabled={busy}>
            {isOpen ? 'Close queue' : 'Open queue'}
          </button>
          <button onClick={onSignOut}>Sign out</button>
        </div>
      </header>

      {error && <p className="error" role="alert">{error}. Retrying…</p>}

      <section className="tiles" aria-label="Today">
        <Tile label="Waiting now" value={board ? String(board.stats.waiting) : '…'} />
        <Tile label="Served today" value={board ? String(board.stats.served_today) : '…'} note={board ? `${board.stats.no_shows_today} no-shows` : ''} />
        <Tile
          label="Average wait today"
          value={board?.stats.avg_wait_minutes_today != null ? `${board.stats.avg_wait_minutes_today} min` : '–'}
          note="from joining to being called"
        />
        <Tile label="Average service" value={board ? `${board.stats.avg_service_minutes} min` : '…'} note="last 7 days" />
      </section>

      <div className="grid">
        <section className="card desk" aria-labelledby="desk-h">
          <h2 id="desk-h">Your desk</h2>
          <label>
            You are at
            <select value={counter} onChange={(e) => setCounter(e.target.value)}>
              {COUNTERS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <button
            className="primary big"
            disabled={busy || !board || board.waiting.length === 0}
            onClick={() => act(() => api.callNext(queue.id, counter))}
          >
            {board && board.waiting.length === 0 ? 'Nobody waiting' : `Call next to ${counter}`}
          </button>
          {mine.map((t) => (
            <div key={t.id} className="serving">
              <div className="num">{pad(t.number)}</div>
              <div className="grow">
                <strong>{t.name}</strong>
                <div className="muted small">Called {clock(t.called_at)}</div>
              </div>
              <button className="good" disabled={busy} onClick={() => act(() => api.finish(queue.id, t.id, 'served'))}>Served</button>
              <button disabled={busy} onClick={() => act(() => api.finish(queue.id, t.id, 'no_show'))}>No-show</button>
            </div>
          ))}
          {notice && <p className="notice" role="status">{notice}</p>}
          <div className="links small">
            <a href={joinUrl} target="_blank" rel="noopener">Open the customer join page ↗</a>
            <a href={displayUrl} target="_blank" rel="noopener">Open the waiting-room screen ↗</a>
          </div>
        </section>

        <section className="card" aria-labelledby="wait-h">
          <div className="row between">
            <h2 id="wait-h">Waiting ({board?.waiting.length ?? 0})</h2>
            <button className="small-btn" disabled={busy} onClick={() => act(() => api.sampleWalkIns(queue.id), 'Added 5 walk-ins')}>
              + Add 5 sample walk-ins
            </button>
          </div>
          {board && board.waiting.length === 0 && <p className="muted">Nobody is waiting. Add sample walk-ins or open the join page.</p>}
          <ol className="list">
            {board?.waiting.map((t, i) => (
              <li key={t.id}>
                <span className="num-sm">{pad(t.number)}</span>
                <span className="grow">{t.name}</span>
                <span className="muted small">{i === 0 ? 'next' : `${minutesSince(t.joined_at)} min`}</span>
                <button className="small-btn" disabled={busy} onClick={() => act(() => api.finish(queue.id, t.id, 'cancelled'))} aria-label={`Remove ${t.name}`}>
                  Remove
                </button>
              </li>
            ))}
          </ol>
        </section>

        <section className="card" aria-labelledby="now-h">
          <h2 id="now-h">Now serving</h2>
          {board && board.now_serving.length === 0 && <p className="muted">No one has been called yet.</p>}
          <ul className="list">
            {board?.now_serving.map((t) => <TicketRow key={t.id} t={t} right={t.counter ?? ''} />)}
          </ul>
          <h2 className="mt">Recently finished</h2>
          <ul className="list">
            {board?.recent.map((t) => (
              <TicketRow key={t.id} t={t} right={`${t.status === 'served' ? 'Served' : t.status === 'no_show' ? 'No-show' : 'Left'} ${clock(t.finished_at)}`} />
            ))}
          </ul>
        </section>
      </div>
      <footer className="muted small foot">
        Updates every 3 seconds · <a href="https://github.com/NusratBegum/queueflow">Source on GitHub</a> · Built by{' '}
        <a href="https://nusratbegum.dev">Nusrat Begum</a>
      </footer>
    </div>
  );
}

function TicketRow({ t, right }: { t: Ticket; right: string }) {
  return (
    <li>
      <span className="num-sm">{pad(t.number)}</span>
      <span className="grow">{t.name}</span>
      <span className="muted small">{right}</span>
    </li>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="card tile">
      <div className="muted small">{label}</div>
      <div className="tile-value">{value}</div>
      {note && <div className="muted small">{note}</div>}
    </div>
  );
}

export function Logo() {
  return (
    <svg className="logo" width="22" height="22" viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="currentColor" />
      <circle cx="9" cy="16" r="3" fill="var(--surface)" />
      <circle cx="16" cy="16" r="3" fill="var(--surface)" opacity=".75" />
      <circle cx="23" cy="16" r="3" fill="var(--surface)" opacity=".5" />
    </svg>
  );
}
