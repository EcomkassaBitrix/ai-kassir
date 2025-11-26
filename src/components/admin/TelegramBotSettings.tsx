import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from '@/components/ui/icon';
import { toast } from 'sonner';

export const TelegramBotSettings = () => {
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
