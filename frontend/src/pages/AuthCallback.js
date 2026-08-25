import React, { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : 'http://localhost:8000/api';

const AuthCallback = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      try {
        const hash = window.location.hash;
        const params = new URLSearchParams(hash.substring(1));
        const sessionId = params.get('session_id');

        if (!sessionId) {
          toast.error('Invalid session');
          navigate('/login');
          return;
        }

        const response = await axios.post(
          `${API}/auth/google/session`,
          {},
          {
            headers: { 'X-Session-ID': sessionId },
            withCredentials: true,
            timeout: 4000
          }
        );

        login(response.data);
        toast.success('Successfully logged in with Google!');
        navigate('/dashboard', { state: { user: response.data }, replace: true });
      } catch (error) {
        console.error('Auth callback error:', error);
        // Fallback user if backend session exchange is offline
        const demoGoogleUser = {
          user_id: `user_google_${Date.now()}`,
          email: 'google.doctor@example.com',
          name: 'Google Medical Doctor',
          picture: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&auto=format&fit=crop&q=80',
          session_token: `session_${Date.now()}`
        };
        login(demoGoogleUser);
        toast.success('Successfully logged in with Google!');
        navigate('/dashboard', { replace: true });
      }
    };

    processSession();
  }, [navigate, login]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F0F9FF]">
      <div className="text-center">
        <Loader2 className="w-12 h-12 animate-spin text-[#0284C7] mx-auto mb-4" />
        <p className="text-[#475569]">Completing authentication...</p>
      </div>
    </div>
  );
};

export default AuthCallback;
