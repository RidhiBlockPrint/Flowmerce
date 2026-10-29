// The frontend only talks to the Python API through /api/*; it holds no credentials of its own.
const API_ORIGIN = process.env.FLOWMERCE_API_ORIGIN || 'http://127.0.0.1:8787';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${API_ORIGIN}/api/:path*` }];
  },
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'same-origin' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
      ],
    }];
  },
  async redirects() {
    // Local operator mode has no sign-in: the old address goes straight to Home.
    return [{ source: '/login', destination: '/', permanent: false }];
  },
};

export default nextConfig;
