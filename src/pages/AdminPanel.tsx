import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { toast } from 'sonner';
import { AISettingsSectionNew } from '@/components/settings/AISettingsSectionNew';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

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
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    if (!token) {
      navigate('/admin-login');
      return;
    }

    setAdminToken(token);
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
        navigate('/admin-login');
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

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    navigate('/admin-login');
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
          <TabsList className="grid w-full grid-cols-2 mb-8">
            <TabsTrigger value="stats">Статистика фидбека</TabsTrigger>
            <TabsTrigger value="ai">Настройки ИИ</TabsTrigger>
          </TabsList>

          <TabsContent value="stats">

        {stats && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <Card className="p-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center">
                    <Icon name="MessageSquare" size={24} className="text-blue-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Всего отзывов</p>
                    <p className="text-2xl font-bold">{stats.total}</p>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-green-500/10 rounded-lg flex items-center justify-center">
                    <Icon name="ThumbsUp" size={24} className="text-green-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Положительных</p>
                    <p className="text-2xl font-bold">{stats.positive}</p>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-red-500/10 rounded-lg flex items-center justify-center">
                    <Icon name="ThumbsDown" size={24} className="text-red-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Отрицательных</p>
                    <p className="text-2xl font-bold">{stats.negative}</p>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-purple-500/10 rounded-lg flex items-center justify-center">
                    <Icon name="TrendingUp" size={24} className="text-purple-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Рейтинг</p>
                    <p className="text-2xl font-bold">{stats.positive_rate}%</p>
                  </div>
                </div>
              </Card>
            </div>

            <Card className="p-6">
              <h2 className="text-xl font-bold mb-4">Последние отзывы</h2>
              <div className="space-y-4">
                {stats.recent_feedback.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Отзывов пока нет</p>
                ) : (
                  stats.recent_feedback.map((item, index) => (
                    <div
                      key={`${item.message_id}-${index}`}
                      className="border rounded-lg p-4 hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 space-y-2">
                          <div>
                            <p className="text-xs text-muted-foreground mb-1">Вопрос пользователя:</p>
                            <p className="text-sm">{item.user_message || 'Нет данных'}...</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground mb-1">Ответ ассистента:</p>
                            <p className="text-sm text-muted-foreground">{item.agent_response || 'Нет данных'}...</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm ${
                            item.feedback_type === 'positive' 
                              ? 'bg-green-500/10 text-green-600' 
                              : 'bg-red-500/10 text-red-600'
                          }`}>
                            <Icon 
                              name={item.feedback_type === 'positive' ? 'ThumbsUp' : 'ThumbsDown'} 
                              size={14} 
                            />
                            <span className="capitalize">{item.feedback_type === 'positive' ? 'Хорошо' : 'Плохо'}</span>
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {new Date(item.created_at).toLocaleString('ru-RU')}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </>
        )}
          </TabsContent>

          <TabsContent value="ai">
            <AISettingsSectionNew adminToken={adminToken} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminPanel;