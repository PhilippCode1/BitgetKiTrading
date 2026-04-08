/**
 * @jest-environment jsdom
 */

import {
  computeReconnectDelayMs,
  startManagedLiveEventSource,
} from "@/lib/live-event-source";

describe("computeReconnectDelayMs", () => {
  it("steigt mit Versuch und bleibt unter Cap", () => {
    const a0 = computeReconnectDelayMs(0);
    const a3 = computeReconnectDelayMs(3);
    expect(a3).toBeGreaterThanOrEqual(a0);
    expect(a3).toBeLessThanOrEqual(30_000);
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
});
