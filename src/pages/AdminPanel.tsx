import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-purple-950/20 flex items-center justify-center p-4">
        <Card className="w-full max-w-md p-8">
          <div className="flex flex-col items-center mb-6">
            <div className="w-16 h-16 bg-purple-500/10 rounded-full flex items-center justify-center mb-4">
              <Icon name="Lock" size={32} className="text-purple-500" />
            </div>
            <h1 className="text-2xl font-bold">Админ-панель</h1>
            <p className="text-sm text-muted-foreground mt-1">Введите пароль для входа</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <Input
                type="password"
                placeholder="Введите пароль"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full"
                disabled={loginLoading}
              />
            </div>

            <Button
              type="submit"
              className="w-full"
              disabled={loginLoading || !password}
            >
              {loginLoading ? 'Проверка...' : 'Войти'}
            </Button>
          </form>
        </Card>
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
          <TabsList className="grid w-full grid-cols-3 mb-8">
            <TabsTrigger value="stats">Статистика фидбека</TabsTrigger>
            <TabsTrigger value="ai">Настройки ИИ</TabsTrigger>
            <TabsTrigger value="telegram">Telegram бот</TabsTrigger>
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

          <TabsContent value="telegram">
            <TelegramBotSettings />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

const TelegramBotSettings = () => {
  const [webhookStatus, setWebhookStatus] = useState<string | null>(null);
  const [botToken, setBotToken] = useState('');
  const [checking, setChecking] = useState(false);
  const [setting, setSetting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const webhookUrl = 'https://functions.poehali.dev/c931c0bd-bad6-4f16-9a76-f67296c311b1';
  const tokenApiUrl = 'https://functions.poehali.dev/1772f7f7-7ca3-404c-9472-9f7b3e502238';

  useEffect(() => {
    loadToken();
  }, []);

  const loadToken = async () => {
    const adminToken = localStorage.getItem('admin_token');
    if (!adminToken) return;

    try {
      const response = await fetch(tokenApiUrl, {
        headers: { 'X-Admin-Token': adminToken }
      });

      if (response.ok) {
        const data = await response.json();
        setBotToken(data.token || '');
      }
    } catch (error) {
      console.error('Failed to load token');
    } finally {
      setLoading(false);
    }
  };

  const saveToken = async () => {
    if (!botToken) {
      toast.error('Введите токен бота');
      return;
    }

    const adminToken = localStorage.getItem('admin_token');
    if (!adminToken) return;

    setSaving(true);
    try {
      const response = await fetch(tokenApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': adminToken
        },
        body: JSON.stringify({ token: botToken })
      });

      if (response.ok) {
        toast.success('Токен сохранён');
      } else {
        toast.error('Ошибка сохранения');
      }
    } catch (error) {
      toast.error('Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const checkWebhook = async () => {
    if (!botToken) {
      toast.error('Введите токен бота');
      return;
    }

    setChecking(true);
    try {
      const response = await fetch(`https://api.telegram.org/bot${botToken}/getWebhookInfo`);
      const data = await response.json();

      if (data.ok) {
        const info = data.result;
        if (info.url === webhookUrl) {
          setWebhookStatus('✅ Webhook настроен правильно');
          toast.success('Webhook активен');
        } else if (info.url) {
          setWebhookStatus(`⚠️ Webhook указывает на: ${info.url}`);
          toast.warning('Webhook настроен на другой URL');
        } else {
          setWebhookStatus('❌ Webhook не настроен');
          toast.error('Webhook не настроен');
        }
      }
    } catch (error) {
      toast.error('Ошибка проверки webhook');
    } finally {
      setChecking(false);
    }
  };

  const setupWebhook = async () => {
    if (!botToken) {
      toast.error('Введите токен бота');
      return;
    }

    setSetting(true);
    try {
      const response = await fetch(
        `https://api.telegram.org/bot${botToken}/setWebhook?url=${webhookUrl}`
      );
      const data = await response.json();

      if (data.ok) {
        setWebhookStatus('✅ Webhook настроен успешно');
        toast.success('Webhook настроен! Бот готов к работе');
      } else {
        toast.error(`Ошибка: ${data.description}`);
      }
    } catch (error) {
      toast.error('Ошибка настройки webhook');
    } finally {
      setSetting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center">
            <Icon name="Send" size={24} className="text-blue-500" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Telegram бот</h2>
            <p className="text-sm text-muted-foreground">Настройка интеграции с Telegram</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Токен бота</label>
            <Input
              type="password"
              placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Получите токен у <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">@BotFather</a>
            </p>
          </div>

          <Button
            onClick={saveToken}
            disabled={saving || !botToken}
            className="w-full"
          >
            <Icon name="Save" size={16} className="mr-2" />
            {saving ? 'Сохранение...' : 'Сохранить токен'}
          </Button>

          <div className="flex gap-2">
            <Button
              onClick={checkWebhook}
              disabled={checking || !botToken}
              variant="outline"
              className="flex-1"
            >
              <Icon name="Search" size={16} className="mr-2" />
              {checking ? 'Проверка...' : 'Проверить webhook'}
            </Button>
            <Button
              onClick={setupWebhook}
              disabled={setting || !botToken}
              className="flex-1"
            >
              <Icon name="Check" size={16} className="mr-2" />
              {setting ? 'Настройка...' : 'Настроить webhook'}
            </Button>
          </div>

          {webhookStatus && (
            <div className="p-4 bg-muted rounded-lg">
              <p className="text-sm">{webhookStatus}</p>
            </div>
          )}

          <div className="border-t pt-4">
            <h3 className="font-medium mb-2">Webhook URL:</h3>
            <code className="text-xs bg-muted p-2 rounded block break-all">
              {webhookUrl}
            </code>
          </div>
        </div>
      </Card>

      <Card className="p-6">
        <h3 className="font-bold mb-3">📱 Как использовать бота</h3>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>• Пользователи пишут боту: "Кофе 200р" или "Продал телефон 15000"</p>
          <p>• Бот автоматически создаёт чек через AI</p>
          <p>• Чек отправляется в ЕкомКасса</p>
          <p>• Все чеки сохраняются в базе данных</p>
        </div>
      </Card>
    </div>
  );
};

export default AdminPanel;