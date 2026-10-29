'use client';
import Link from 'next/link';
import { Card, Empty, PageHead } from '../components/ui';
import { Icon } from '../components/Icon';
/**
 * Shared page for every destination that is not built yet. It states plainly what the page is for
 * (from the product handoff) and that it does not exist yet; it offers no buttons that could look
 * like they do something.
 *
 * NOT MOUNTED: local operator mode shows only working pages, so no route renders this component. The source
 * is kept for when a project is built; pass it a registry entry `{ label, purpose, status, note }`.
 */
export default function Planned({ entry }) {
    if (!entry) {
        return <Empty icon="search" title="Page not found">That address does not match any page in the dashboard.</Empty>;
    }
    const future = entry.status === 'future';
    return (<>
      <PageHead crumbs={<Link href="/">Home</Link>} title={entry.label} sub={entry.purpose}/>
      <div className="callout info mb-16" role="note">
        <Icon name="info"/>
        <div>
          {future
            ? <><b>Future scope.</b> This is not an operational project and is not part of the current build plan.</>
            : <><b>Not built yet.</b> This page is planned in the product handoff. There is no data and no controls here until it is built.</>}
        </div>
      </div>
      <Card title={future ? 'About this future-scope project' : 'What this page will hold'}>
        <p>{entry.purpose}</p>
        {entry.note ? <p className="muted mt-8">{entry.note}</p> : null}
        <p className="mt-12"><Link href="/" className="strong"><Icon name="arrowRight" size="sm"/> Back to the Morning Brief</Link></p>
      </Card>
    </>);
}
