import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Brand, BrandFilter, BrandId, Me } from './types';
import { addDays, isoDay } from './format';

interface Range { from: string; to: string; preset: string }

interface AppCtx {
  me: Me;
  refreshMe: () => void;
  can: (perm: string) => boolean;
  brand: BrandFilter;
  setBrand: (b: BrandFilter) => void;
  brandOf: (id: BrandId) => Brand;
  range: Range;
  setRange: (r: Range) => void;
}

const Ctx = createContext<AppCtx | null>(null);

/* Search Console data settles ~3 days after the fact, so ranges end 3 days ago by default. */
export function presetRange(preset: string): Range {
  const to = addDays(isoDay(new Date()), -3);
  const days: Record<string, number> = { '7d': 7, '28d': 28, '3m': 91, '6m': 182, '12m': 365 };
  return { preset, to, from: addDays(to, -((days[preset] ?? 28) - 1)) };
}

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, v: unknown) {
  try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* private mode */ }
}

export function AppProvider({ me, refreshMe, children }: { me: Me; refreshMe: () => void; children: ReactNode }) {
  const [brand, setBrandState] = useState<BrandFilter>(() => load<BrandFilter>('bo.brand', 'all'));
  const [range, setRangeState] = useState<Range>(() => {
    const r = load<Range | null>('bo.range', null);
    return r && r.preset !== 'custom' ? presetRange(r.preset) : r ?? presetRange('28d');
  });
  const setBrand = useCallback((b: BrandFilter) => { setBrandState(b); save('bo.brand', b); }, []);
  const setRange = useCallback((r: Range) => { setRangeState(r); save('bo.range', r); }, []);
  useEffect(() => {
    document.documentElement.dataset.brand = brand;
  }, [brand]);
  const value = useMemo<AppCtx>(() => ({
    me,
    refreshMe,
    can: (p) => me.permissions.includes(p),
    brand,
    setBrand,
    brandOf: (id) => me.brands.find((b) => b.id === id)!,
    range,
    setRange,
  }), [me, refreshMe, brand, setBrand, range, setRange]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useApp outside provider');
  return c;
}

/** Brand query value for API calls: undefined means both. */
export function useBrandParam(): BrandId | undefined {
  const { brand } = useApp();
  return brand === 'all' ? undefined : brand;
}
