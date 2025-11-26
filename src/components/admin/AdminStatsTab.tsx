import { Card } from '@/components/ui/card';
import Icon from '@/components/ui/icon';

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

interface AdminStatsTabProps {
  stats: Stats | null;
}

export const AdminStatsTab = ({ stats }: AdminStatsTabProps) => {
  if (!stats) return null;

  return (
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
            stats.recent_feedback.map((item) => (
              <div key={item.message_id} className="border-b last:border-0 pb-4 last:pb-0">
                <div className="space-y-2">
                  <div className="bg-muted p-3 rounded-lg">
                    <p className="text-sm font-medium mb-1">Вопрос пользователя:</p>
                    <p className="text-sm">{item.user_message}</p>
                  </div>
                  <div className="bg-muted p-3 rounded-lg">
                    <p className="text-sm font-medium mb-1">Ответ агента:</p>
                    <p className="text-sm">{item.agent_response}</p>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Icon
                        name={item.feedback_type === 'positive' ? 'ThumbsUp' : 'ThumbsDown'}
                        size={16}
                        className={item.feedback_type === 'positive' ? 'text-green-500' : 'text-red-500'}
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
  );
};
