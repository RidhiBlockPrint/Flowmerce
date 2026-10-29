import Link from 'next/link';

export const metadata = { title: 'Page not found · Flowmerce' };

export default function NotFound() {
  return (
    <div className="empty" role="alert">
      <h3>Page not found</h3>
      <p>That address does not match any page in Flowmerce.</p>
      <p className="mt-12"><Link href="/" className="strong">Back to Home</Link></p>
    </div>
  );
}
