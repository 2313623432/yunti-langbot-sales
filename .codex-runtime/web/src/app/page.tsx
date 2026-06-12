import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { httpClient, initializeUserInfo } from '@/app/infra/http';

export default function Home() {
  const navigate = useNavigate();
  useEffect(() => {
    httpClient
      .autoLogin()
      .then(async (res) => {
        localStorage.setItem('token', res.token);
        localStorage.setItem('userEmail', res.user);
        await initializeUserInfo();
        navigate('/home/sales');
      })
      .catch(() => navigate('/home/sales'));
  }, []);
  return <div className={``}></div>;
}
