import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { toast } from 'sonner';
import { getUserId } from '@/utils/userId';

const TELEGRAM_LINK_API_URL = 'https://functions.poehali.dev/166ed37e-f4bb-4dbc-8932-b9812f0ba4fd';

export const TelegramLinkSection = () => {
  const [loading, setLoading] = useState(false);
  const [botUrl, setBotUrl] = useState<string | null>(null);

  const generateLink = async () => {
    setLoading(true);
    const userId = getUserId();

    try {
      const response = await fetch(TELEGRAM_LINK_API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': userId
        }
      });

      if (!response.ok) {
        throw new Error('Failed to generate link');
      }

      const data = await response.json();
      setBotUrl(data.bot_url);
      
      window.open(data.bot_url, '_blank');
      toast.success('Ссылка на бота открыта в новой вкладке');
    } catch (error) {
      toast.error('Ошибка создания ссылки');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
          <Icon name="Send" size={24} className="text-blue-500" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-lg mb-1">Telegram бот</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Создавайте чеки прямо из Telegram через бота @ecomkassa_ai_bot
          </p>
          
          <Button
            onClick={generateLink}
            disabled={loading}
            className="w-full"
          >
            <Icon name="Link" size={16} className="mr-2" />
            {loading ? 'Генерация ссылки...' : 'Подключить Telegram бот'}
          </Button>

          {botUrl && (
            <div className="mt-3 p-3 bg-muted rounded-lg">
              <p className="text-xs text-muted-foreground mb-1">Ссылка для повторного подключения:</p>
              <a 
                href={botUrl} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-xs text-blue-500 hover:underline break-all"
              >
                {botUrl}
              </a>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};
