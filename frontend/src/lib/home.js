/**
 * Data behind the Home / Morning Brief page: the real records from GET /api/home. Nothing is invented.
 */
import { useMemo } from 'react';
import { qs, useApi } from './api';
const EMPTY = { kind: 'none', brief: [], metrics: [], approvals: [], approvalsTotal: 0, alerts: [], reports: [], jobs: [], syncs: [] };
/** Home data for the selected brand: the real GET /api/home response. */
export function useHomeData(brand) {
    const live = useApi(`/home${qs({ brand: brand === 'all' ? undefined : brand })}`);
    const real = useMemo(() => (live.data ? { ...live.data, kind: 'api' } : EMPTY), [live.data]);
    return { data: real, loading: live.loading || (!live.data && !live.error), error: live.error, reload: live.reload };
}
