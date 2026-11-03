const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

export type TicketStatus = 'waiting' | 'called' | 'served' | 'no_show' | 'cancelled';

export interface Queue {
  id: number;
  name: string;
  slug: string;
  is_open: boolean;
}

export interface Ticket {
  id: number;
  number: number;
  name: string;
  status: TicketStatus;
  counter: string | null;
  joined_at: string;
  called_at: string | null;
  finished_at: string | null;
}

export interface Board {
  queue: Queue;
  now_serving: Ticket[];
  waiting: Ticket[];
  recent: Ticket[];
  stats: {
    waiting: number;
    served_today: number;
    no_shows_today: number;
    avg_wait_minutes_today: number | null;
    avg_service_minutes: number;
  };
}

export interface PublicQueue {
  name: string;
  slug: string;
  is_open: boolean;
  waiting: number;
  now_serving: { number: number; counter: string | null }[];
  estimated_wait_minutes: number;
}

export interface PublicTicket {
  queue_name: string;
  queue_slug: string;
  number: number;
  name: string;
  status: TicketStatus;
  counter: string | null;
  people_ahead: number;
  estimated_wait_minutes: number;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN_KEY = 'queueflow-staff-token';
let token: string | null = sessionStorage.getItem(TOKEN_KEY);

export const isLoggedIn = () => token !== null;

export function logout() {
  token = null;
  sessionStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !(init.body instanceof URLSearchParams)) headers.set('Content-Type', 'application/json');
  const res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });
  if (res.status === 401 && token) logout();
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === 'string' ? body.detail : 'Please check the form and try again';
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  const res = await request<{ access_token: string }>('/auth/token', { method: 'POST', body });
  token = res.access_token;
  sessionStorage.setItem(TOKEN_KEY, token);
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  queues: () => request<Queue[]>('/queues'),
  board: (queueId: number) => request<Board>(`/queues/${queueId}/board`),
  setOpen: (queueId: number, is_open: boolean) => request<Queue>(`/queues/${queueId}`, json('PATCH', { is_open })),
  callNext: (queueId: number, counter: string) => request<Ticket>(`/queues/${queueId}/call-next`, json('POST', { counter })),
  finish: (queueId: number, ticketId: number, status: 'served' | 'no_show' | 'cancelled') =>
    request<Ticket>(`/queues/${queueId}/tickets/${ticketId}`, json('PATCH', { status })),
  sampleWalkIns: (queueId: number) => request<Ticket[]>(`/queues/${queueId}/sample-walk-ins`, json('POST')),
  publicQueue: (slug: string) => request<PublicQueue>(`/public/queues/${encodeURIComponent(slug)}`),
  join: (slug: string, name: string) =>
    request<{ number: number; token: string }>(`/public/queues/${encodeURIComponent(slug)}/tickets`, json('POST', { name })),
  ticket: (tok: string) => request<PublicTicket>(`/public/tickets/${encodeURIComponent(tok)}`),
  leave: (tok: string) => request<void>(`/public/tickets/${encodeURIComponent(tok)}/cancel`, json('POST')),
};
