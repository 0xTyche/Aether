/** Reconnecting WebSocket client for the Aether `/ws` channel.
 *
 * Single connection per page. Auto-reconnect with exponential backoff
 * capped at 30s. Re-subscribes to the requested channels on every
 * reconnect so the consumer doesn't have to track session state.
 */

import type { WSChannel, WSServerMessage } from "../types/api";

type Handler = (msg: WSServerMessage) => void;

export interface WSClientOptions {
  url?: string;
  channels?: WSChannel[];
  onMessage: Handler;
  onOpen?: () => void;
  onClose?: () => void;
}

export class WSClient {
  private url: string;
  private channels: WSChannel[];
  private onMessage: Handler;
  private onOpen?: () => void;
  private onClose?: () => void;
  private ws: WebSocket | null = null;
  private backoffMs = 500;
  private readonly backoffMaxMs = 30_000;
  private stopped = false;
  private pingInterval: number | null = null;

  constructor(opts: WSClientOptions) {
    this.url = opts.url ?? this.defaultUrl();
    this.channels = opts.channels ?? ["events", "prices"];
    this.onMessage = opts.onMessage;
    this.onOpen = opts.onOpen;
    this.onClose = opts.onClose;
  }

  private defaultUrl(): string {
    if (typeof window === "undefined") return "ws://127.0.0.1:8000/ws";
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws`;
  }

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.pingInterval !== null) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.ws) {
      try { this.ws.close(); } catch { /* ignore */ }
      this.ws = null;
    }
  }

  private connect(): void {
    if (this.stopped) return;
    const ws = new WebSocket(this.url);
    this.ws = ws;

    ws.addEventListener("open", () => {
      this.backoffMs = 500;
      ws.send(JSON.stringify({ type: "subscribe", channels: this.channels }));
      this.pingInterval = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping", ts: String(Date.now()) }));
        }
      }, 25_000);
      this.onOpen?.();
    });

    ws.addEventListener("message", (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WSServerMessage;
        this.onMessage(msg);
      } catch {
        // ignore non-JSON frames
      }
    });

    ws.addEventListener("close", () => {
      if (this.pingInterval !== null) {
        clearInterval(this.pingInterval);
        this.pingInterval = null;
      }
      this.onClose?.();
      if (!this.stopped) {
        const delay = this.backoffMs;
        this.backoffMs = Math.min(this.backoffMs * 2, this.backoffMaxMs);
        setTimeout(() => this.connect(), delay);
      }
    });

    ws.addEventListener("error", () => {
      try { ws.close(); } catch { /* ignore */ }
    });
  }
}
