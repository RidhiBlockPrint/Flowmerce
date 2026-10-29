import { Link, useLocation } from 'react-router-dom';
import { Card, Empty, PageHead } from '../components/ui';
import { StatusChip } from '../components/home';
import { Icon } from '../components/Icon';
import { entryFor } from '../lib/routes';

/**
 * Shared page for every destination that is not built yet. It states plainly what the page is for
 * (from the product handoff) and that it does not exist yet; it offers no buttons that could look
 * like they do something.
 */
export default function Planned() {
  const { pathname } = useLocation();
  const entry = entryFor(pathname);
  if (!entry) {
    return <Empty icon="search" title="Page not found">That address does not match any page in the dashboard.</Empty>;
  }
  const future = entry.status === 'future';
  return (
    <>
      <PageHead
        crumbs={<Link to="/">Home</Link>}
        title={<>{entry.label} <StatusChip status={entry.status} /></>}
        sub={entry.purpose}
      />
      <div className="callout info mb-16" role="note">
        <Icon name="info" />
        <div>
          {future
            ? <><b>Future scope.</b> This is not an operational project and is not part of the current build plan.</>
            : <><b>Not built yet.</b> This page is planned in the product handoff. There is no data and no controls here until it is built.</>}
        </div>
      </div>
      <Card title={future ? 'About this future-scope project' : 'What this page will hold'}>
        <p>{entry.purpose}</p>
        {entry.note ? <p className="muted mt-8">{entry.note}</p> : null}
        <p className="mt-12"><Link to="/" className="strong"><Icon name="arrowRight" size="sm" /> Back to the Morning Brief</Link></p>
      </Card>
    </>
  );
}
