import { useCallback, useEffect, useRef, useState } from 'react';

/** Load data now and every `ms` while the tab is visible. */
export function usePoll<T>(load: () => Promise<T>, ms: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadRef = useRef(load);
  loadRef.current = load;

  const refresh = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the server');
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') refresh();
    }, ms);
    const onVisible = () => document.visibilityState === 'visible' && refresh();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [ms, refresh]);

  return { data, error, refresh };
}
