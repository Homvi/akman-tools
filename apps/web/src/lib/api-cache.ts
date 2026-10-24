/** In-memory GET cache with in-flight dedupe (no external deps). */

type Entry = { at: number; data: unknown };

const store = new Map<string, Entry>();
const inflight = new Map<string, Promise<unknown>>();

const DEFAULT_TTL_MS = 45_000;

export async function cachedGet<T>(
  path: string,
  fetcher: () => Promise<T>,
  ttlMs: number = DEFAULT_TTL_MS
): Promise<T> {
  const hit = store.get(path);
  if (hit && Date.now() - hit.at < ttlMs) {
    return hit.data as T;
  }
  const pending = inflight.get(path);
  if (pending) {
    return pending as Promise<T>;
  }
  const promise = fetcher()
    .then((data) => {
      store.set(path, { at: Date.now(), data });
      inflight.delete(path);
      return data;
    })
    .catch((err) => {
      inflight.delete(path);
      throw err;
    });
  inflight.set(path, promise);
  return promise;
}

/** Drop cache entries whose path starts with `prefix` (or all if omitted). */
export function invalidateApiCache(prefix?: string): void {
  if (!prefix) {
    store.clear();
    return;
  }
  for (const key of [...store.keys()]) {
    if (key === prefix || key.startsWith(prefix)) {
      store.delete(key);
    }
  }
}

export function peekApiCache<T>(path: string): T | undefined {
  const hit = store.get(path);
  return hit ? (hit.data as T) : undefined;
}

/** Write/update a cache entry (e.g. after optimistic patch). */
export function setApiCache<T>(path: string, data: T): void {
  store.set(path, { at: Date.now(), data });
}
