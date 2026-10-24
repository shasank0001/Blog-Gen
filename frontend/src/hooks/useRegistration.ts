import { useEffect, useState } from 'react';
import { getAuthConfig } from '@/lib/api';

export function useRegistration() {
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    getAuthConfig().then(config => { if (active) setAllowed(config.allow_registration); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);
  return { allowed, error };
}
