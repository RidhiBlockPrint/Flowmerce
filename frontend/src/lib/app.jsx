'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { addDays, isoDay } from './format';
const Ctx = createContext(null);
/* Search Console data settles ~3 days after the fact, so ranges end 3 days ago by default. */
export function presetRange(preset) {
    const to = addDays(isoDay(new Date()), -3);
    const days = { '7d': 7, '28d': 28, '3m': 91, '6m': 182, '12m': 365 };
    return { preset, to, from: addDays(to, -((days[preset] ?? 28) - 1)) };
}
function load(key, fallback) {
    try {
        const v = localStorage.getItem(key);
        return v ? JSON.parse(v) : fallback;
    }
    catch {
        return fallback;
    }
}
function save(key, v) {
    try {
        localStorage.setItem(key, JSON.stringify(v));
    }
    catch { /* private mode */ }
}
export function AppProvider({ me, refreshMe, children }) {
    const [brand, setBrandState] = useState(() => load('bo.brand', 'all'));
    const [range, setRangeState] = useState(() => {
        const r = load('bo.range', null);
        return r && r.preset !== 'custom' ? presetRange(r.preset) : r ?? presetRange('28d');
    });
    const setBrand = useCallback((b) => { setBrandState(b); save('bo.brand', b); }, []);
    const setRange = useCallback((r) => { setRangeState(r); save('bo.range', r); }, []);
    useEffect(() => {
        document.documentElement.dataset.brand = brand;
    }, [brand]);
    const value = useMemo(() => ({
        me,
        refreshMe,
        can: (p) => me.permissions.includes(p),
        brand,
        setBrand,
        brandOf: (id) => me.brands.find((b) => b.id === id),
        range,
        setRange,
    }), [me, refreshMe, brand, setBrand, range, setRange]);
    return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export function useApp() {
    const c = useContext(Ctx);
    if (!c)
        throw new Error('useApp outside provider');
    return c;
}
/** Brand query value for API calls: undefined means both. */
export function useBrandParam() {
    const { brand } = useApp();
    return brand === 'all' ? undefined : brand;
}
