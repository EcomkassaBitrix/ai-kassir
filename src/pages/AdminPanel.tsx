import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { toast } from 'sonner';
import { AISettingsSectionNew } from '@/components/settings/AISettingsSectionNew';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AdminLoginForm } from '@/components/admin/AdminLoginForm';
import { AdminStatsTab } from '@/components/admin/AdminStatsTab';
import { TelegramBotSettings } from '@/components/admin/TelegramBotSettings';

interface FeedbackItem {
  message_id: string;
  user_message: string;
  agent_response: string;
  feedback_type: 'positive' | 'negative';
  created_at: string;
}

interface Stats {
  total: number;
  positive: number;
  negative: number;
  positive_rate: number;
  recent_feedback: FeedbackItem[];
}

export const AdminPanel = () => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [adminToken, setAdminToken] = useState<string>('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    if (!token) {
      setIsAuthenticated(false);
      setLoading(false);
      return;
    }

    setAdminToken(token);
    setIsAuthenticated(true);
    loadStats(token);
  }, [navigate]);

  const loadStats = async (token: string) => {
    try {
      const response = await fetch('https://functions.poehali.dev/3816b065-d7fe-4f0b-bd74-1ae24e865355', {
        headers: {
          'X-Admin-Token': token
        }
      });

      if (response.status === 401) {
        localStorage.removeItem('admin_token');
        setIsAuthenticated(false);
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to load stats');
      }

      const data = await response.json();
      setStats(data);
    } catch (error) {
      toast.error('Ошибка загрузки статистики');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);

    try {
      const response = await fetch('https://functions.poehali.dev/9e5db515-a0fc-4981-9d4f-6f4fd56861b2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });

      const data = await response.json();

      if (response.ok && data.token) {
        localStorage.setItem('admin_token', data.token);
        setAdminToken(data.token);
        setIsAuthenticated(true);
        toast.success('Вход выполнен');
        await loadStats(data.token);
      } else {
        toast.error('Неверный пароль');
      }
    } catch (error) {
      toast.error('Ошибка подключения');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    setIsAuthenticated(false);
    setPassword('');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-purple-950/20 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto mb-4"></div>
          <p className="text-muted-foreground">Загрузка...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <AdminLoginForm
        password={password}
        loginLoading={loginLoading}
        onPasswordChange={setPassword}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-purple-950/20 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold mb-2">Админ-панель</h1>
            <p className="text-muted-foreground">Управление системой</p>
          </div>
          <Button variant="outline" onClick={handleLogout}>
            <Icon name="LogOut" size={16} className="mr-2" />
            Выйти
          </Button>
        </div>

        <Tabs defaultValue="stats" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-8">
            <TabsTrigger value="stats">Статистика фидбека</TabsTrigger>
            <TabsTrigger value="ai">Настройки ИИ</TabsTrigger>
            <TabsTrigger value="telegram">Telegram бот</TabsTrigger>
          </TabsList>

          <TabsContent value="stats">
            <AdminStatsTab stats={stats} />
          </TabsContent>

          <TabsContent value="ai">
            <AISettingsSectionNew adminToken={adminToken} />
          </TabsContent>

          <TabsContent value="telegram">
            <TelegramBotSettings />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminPanel;
