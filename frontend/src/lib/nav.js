'use client';
/**
 * Thin helpers over the Next.js App Router (next/navigation) that keep the page code short:
 * `useNavigate()` pushes a route, `useSearchParams()` returns [params, setParams] where setParams
 * rewrites the query string of the current page (optionally replacing the history entry).
 */
import { usePathname, useRouter, useSearchParams as useNextSearchParams } from 'next/navigation';
import { useCallback } from 'react';

export { useParams, usePathname } from 'next/navigation';

export function useNavigate() {
  const router = useRouter();
  return useCallback((to) => router.push(to), [router]);
}

export function useSearchParams() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useNextSearchParams();
  const setSp = useCallback((next, opts = {}) => {
    const q = new URLSearchParams(next).toString();
    const url = q ? `${pathname}?${q}` : pathname;
    if (opts.replace) router.replace(url, { scroll: false });
    else router.push(url);
  }, [router, pathname]);
  return [sp, setSp];
}
