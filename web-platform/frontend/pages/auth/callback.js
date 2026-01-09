import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/layout/Layout';

export default function AuthCallback() {
  const router = useRouter();
  const { token, error } = router.query;

  useEffect(() => {
    if (token) {
      // Store token in localStorage
      localStorage.setItem('auth_token', token);

      // Redirect to homepage
      setTimeout(() => {
        router.push('/');
      }, 1000);
    } else if (error) {
      // Redirect to login with error
      setTimeout(() => {
        router.push(`/login?error=${error}`);
      }, 2000);
    }
  }, [token, error, router]);

  return (
    <Layout title="Authentication - FUT Hub">
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          {token ? (
            <>
              <div className="mb-4">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Login Successful!</h2>
              <p className="text-gray-600">Redirecting you to the homepage...</p>
            </>
          ) : error ? (
            <>
              <div className="text-red-600 text-5xl mb-4">✕</div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Authentication Failed</h2>
              <p className="text-gray-600 mb-4">
                {error === 'no_code' && 'No authorization code received'}
                {error === 'auth_failed' && 'Failed to authenticate with Discord'}
                {!error.match(/no_code|auth_failed/) && 'An error occurred during authentication'}
              </p>
              <p className="text-gray-500">Redirecting you back to login...</p>
            </>
          ) : (
            <>
              <div className="mb-4">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
              </div>
              <p className="text-gray-600">Processing authentication...</p>
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
