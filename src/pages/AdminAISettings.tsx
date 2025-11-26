import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Loader2, LogOut, Save } from 'lucide-react';
import Icon from '@/components/ui/icon';

interface UserAISettings {
  user_id: string;
  active_ai_provider: string;
  gigachat_auth_key: string;
  yandexgpt_api_key: string;
  yandexgpt_folder_id: string;
  gptunnel_api_key: string;
}

const AI_PROVIDERS = [
  { id: '', name: 'Не выбран' },
  { id: 'gigachat', name: 'GigaChat (Сбер)' },
  { id: 'yandexgpt', name: 'YandexGPT' },
  { id: 'gptunnel', name: 'GPT Tunnel (Claude)' }
];

const AdminAISettings = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [users, setUsers] = useState<UserAISettings[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [formData, setFormData] = useState<UserAISettings>({
    user_id: '',
    active_ai_provider: '',
    gigachat_auth_key: '',
    yandexgpt_api_key: '',
    yandexgpt_folder_id: '',
    gptunnel_api_key: ''
  });

  const adminPassword = localStorage.getItem('admin_password');

  useEffect(() => {
    if (!adminPassword) {
      navigate('/admin-login');
      return;
    }
    loadUsers();
  }, [adminPassword, navigate]);

  const loadUsers = async () => {
    try {
      const response = await fetch('https://functions.poehali.dev/d86cb777-6d38-4618-beb4-7bc088661121', {
        method: 'GET',
        headers: {
          'X-Admin-Password': adminPassword!
        }
      });

      if (response.status === 401) {
        localStorage.removeItem('admin_password');
        navigate('/admin-login');
        return;
      }

      const data = await response.json();
      setUsers(data.users || []);
    } catch (error) {
      toast.error('Ошибка загрузки пользователей');
    } finally {
      setLoading(false);
    }
  };

  const handleUserSelect = (userId: string) => {
    setSelectedUser(userId);
    const user = users.find(u => u.user_id === userId);
    if (user) {
      setFormData(user);
    }
  };

  const handleSave = async () => {
    if (!selectedUser) {
      toast.error('Выберите пользователя');
      return;
    }

    setSaving(true);
    try {
      const response = await fetch('https://functions.poehali.dev/d86cb777-6d38-4618-beb4-7bc088661121', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Password': adminPassword!
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        toast.success('Настройки сохранены');
        await loadUsers();
      } else {
        toast.error('Ошибка сохранения настроек');
      }
    } catch (error) {
      toast.error('Ошибка сохранения настроек');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_password');
    navigate('/admin-login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Админка AI Провайдеров</h1>
            <p className="text-gray-600 mt-1">Управление AI провайдерами для всех пользователей</p>
          </div>
          <Button variant="outline" onClick={handleLogout}>
            <Icon name="LogOut" className="mr-2 h-4 w-4" />
            Выйти
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Выбор пользователя</CardTitle>
            <CardDescription>Выберите пользователя для настройки AI провайдера</CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={selectedUser} onValueChange={handleUserSelect}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите пользователя" />
              </SelectTrigger>
              <SelectContent>
                {users.map(user => (
                  <SelectItem key={user.user_id} value={user.user_id}>
                    {user.user_id} {user.active_ai_provider && `(${AI_PROVIDERS.find(p => p.id === user.active_ai_provider)?.name})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {selectedUser && (
          <Card>
            <CardHeader>
              <CardTitle>Настройки AI провайдера для {selectedUser}</CardTitle>
              <CardDescription>Выберите провайдер и укажите ключи доступа</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>AI Провайдер</Label>
                <Select 
                  value={formData.active_ai_provider} 
                  onValueChange={(value) => setFormData({...formData, active_ai_provider: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите провайдер" />
                  </SelectTrigger>
                  <SelectContent>
                    {AI_PROVIDERS.map(provider => (
                      <SelectItem key={provider.id} value={provider.id}>
                        {provider.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {formData.active_ai_provider === 'gigachat' && (
                <div className="space-y-2">
                  <Label>GigaChat Authorization Key</Label>
                  <Input
                    type="password"
                    value={formData.gigachat_auth_key}
                    onChange={(e) => setFormData({...formData, gigachat_auth_key: e.target.value})}
                    placeholder="Введите Authorization Key"
                  />
                </div>
              )}

              {formData.active_ai_provider === 'yandexgpt' && (
                <>
                  <div className="space-y-2">
                    <Label>Yandex API Key</Label>
                    <Input
                      type="password"
                      value={formData.yandexgpt_api_key}
                      onChange={(e) => setFormData({...formData, yandexgpt_api_key: e.target.value})}
                      placeholder="Введите API Key"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Yandex Folder ID</Label>
                    <Input
                      value={formData.yandexgpt_folder_id}
                      onChange={(e) => setFormData({...formData, yandexgpt_folder_id: e.target.value})}
                      placeholder="Введите Folder ID"
                    />
                  </div>
                </>
              )}

              {formData.active_ai_provider === 'gptunnel' && (
                <div className="space-y-2">
                  <Label>GPT Tunnel API Key</Label>
                  <Input
                    type="password"
                    value={formData.gptunnel_api_key}
                    onChange={(e) => setFormData({...formData, gptunnel_api_key: e.target.value})}
                    placeholder="Введите API Key"
                  />
                </div>
              )}

              <Button onClick={handleSave} disabled={saving} className="w-full">
                {saving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Сохранение...
                  </>
                ) : (
                  <>
                    <Icon name="Save" className="mr-2 h-4 w-4" />
                    Сохранить настройки
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default AdminAISettings;
