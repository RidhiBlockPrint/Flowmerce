/** Shared shipping constants. Colours reuse the Flowmerce palette (crit / saffron / ok) plus neutral greys. */
export const CATS = {
    red: { label: 'Critical 9+ days', short: 'Critical', color: '#b42318' },
    orange: { label: 'Orange 6-8 days', short: 'Orange', color: '#d9661a' },
    yellow: { label: 'Yellow 4-5 days', short: 'Yellow', color: '#c98a0c' },
    grey: { label: 'Grey 2-3 days', short: 'Grey', color: '#8b8279' },
    on_track: { label: 'On track', short: 'On track', color: '#2d6a3e' },
    no_scan: { label: 'No scan data', short: 'No scan', color: '#6b4fbb' },
    unconfirmed: { label: 'No carrier or tracking', short: 'No tracking', color: '#6b4fbb' },
    lost: { label: 'Lost (team confirmed)', short: 'Lost', color: '#7a1a12' },
    failed: { label: 'Could not deliver (team confirmed)', short: 'Failed', color: '#b25410' },
    delivered: { label: 'Delivered', short: 'Delivered', color: '#2f5d8a' },
    covered: { label: 'Fulfilled by hand, tracked package delivered', short: 'Fulfilled by hand', color: '#4a7a8c' },
};
export const MANUAL = { delivered: 'Delivered', lost: 'Lost', failed: 'Could not deliver', in_transit: 'Still in transit' };
/** Button labels for the team check in the shipment drawer (same wording as the original tracker). */
export const MARK_ACTION = { delivered: 'Mark delivered', lost: 'Mark lost', failed: "Couldn't deliver", in_transit: 'Still in transit' };
export const MCF_LEVEL = { critical: 'Critical · 10+ days', watch: 'Watch · 7+ days', alert: 'Alert · 5+ days' };

/** Order-level groups (see modules/shipping/orders.py). */
export const GROUPS = {
    delivered: { label: 'Delivered', color: '#2f5d8a' },
    in_transit: { label: 'In transit', color: '#2d6a3e' },
    delayed: { label: 'Delayed', color: '#d9661a' },
    not_dispatched: { label: 'Not dispatched', color: '#8b8279' },
    lost_missing: { label: 'Lost / missing', color: '#7a1a12' },
    no_tracking_id: { label: 'No tracking ID', color: '#c98a0c' },
    no_carrier: { label: 'No carrier tracking', color: '#6b4fbb' },
    needs_action: { label: 'Needs action', color: '#b42318' },
};
export const TIERS = {
    yellow: { label: 'Yellow 4-5 days', color: '#c98a0c' },
    orange: { label: 'Orange 6-8 days', color: '#d9661a' },
    red: { label: 'Red 9-12 days', color: '#b42318' },
    critical: { label: 'Critical 13+ days', color: '#7a1a12' },
};
export const FLAGS = {
    no_movement: 'No carrier scan for 5+ days',
    delivered_late: 'Delivered late (13+ days)',
};

export function isShippingPath(pathname) {
    return pathname === '/shipping' || pathname.startsWith('/shipping/');
}
