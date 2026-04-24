/**
 * @jest-environment jsdom
 */

import {
  computeReconnectDelayMs,
  getLiveSseGlobalStatus,
  startManagedLiveEventSource,
} from "@/lib/live-event-source";

describe("computeReconnectDelayMs", () => {
  it("Start ~1s, steigt (Verdopplung) und bleibt unter 30s Cap", () => {
    const a1 = computeReconnectDelayMs(1);
    const a2 = computeReconnectDelayMs(2);
    const a4 = computeReconnectDelayMs(4);
    expect(a1).toBeGreaterThanOrEqual(900);
    expect(a1).toBeLessThanOrEqual(1_100);
    expect(a2).toBeGreaterThanOrEqual(a1);
    expect(a4).toBeLessThanOrEqual(30_000);
  });
});

describe("startManagedLiveEventSource", () => {
  const OriginalES = globalThis.EventSource;

  afterEach(() => {
    globalThis.EventSource = OriginalES;
    jest.useRealTimers();
  });

  it("gibt nach maxReconnectAttempts auf und ruft onGiveUp", async () => {
    jest.useFakeTimers();

    const instances: { onerror: (() => void) | null; close: () => void }[] = [];

    class MockES {
      url: string;
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(url: string) {
        this.url = url;
        instances.push(this);
      }
      addEventListener() {}
      close() {}
    }

    globalThis.EventSource = MockES as unknown as typeof EventSource;

    const onGiveUp = jest.fn();
    const onConnectionState = jest.fn();

    startManagedLiveEventSource({
      symbol: "BTCUSDT",
      timeframe: "1m",
      maxReconnectAttempts: 2,
      onGiveUp,
      onConnectionState,
      handlers: {},
    });

    expect(instances.length).toBe(1);

    for (let i = 0; i < 3; i += 1) {
      const es = instances[instances.length - 1]!;
      es.onerror?.();
      await jest.runAllTimersAsync();
    }

    expect(onGiveUp).toHaveBeenCalledTimes(1);
    const states = onConnectionState.mock.calls.map((c) => c[0]);
    expect(states).toContain("given_up");
  });

  it("DoD: Reconnect-Phase setzt globalen Live-Sse-Status auf RECONNECTING", async () => {
    jest.useFakeTimers();
    const instances: { onerror: (() => void) | null; close: () => void }[] = [];
    class MockES2 {
      url: string;
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(url: string) {
        this.url = url;
        instances.push(this);
      }
      addEventListener() {}
      close() {}
    }
    globalThis.EventSource = MockES2 as unknown as typeof EventSource;

    const c = startManagedLiveEventSource({
      symbol: "ETHUSDT",
      timeframe: "5m",
      maxReconnectAttempts: 99,
      onConnectionState: () => {
        // noop: global status is source of truth for Konsolen-Leiste
      },
      handlers: {},
    });

    expect(getLiveSseGlobalStatus()).toBe("CONNECTING");
    const first = instances[0]!;
    first.onerror?.();
    await Promise.resolve();
    expect(getLiveSseGlobalStatus()).toBe("RECONNECTING");
    c.close();
    expect(getLiveSseGlobalStatus()).toBe("DISCONNECTED");
  });
});
