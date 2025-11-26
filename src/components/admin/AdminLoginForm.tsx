import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from '@/components/ui/icon';

interface AdminLoginFormProps {
  password: string;
  loginLoading: boolean;
  onPasswordChange: (password: string) => void;
  onSubmit: (e: React.FormEvent) => void;
}

export const AdminLoginForm = ({ password, loginLoading, onPasswordChange, onSubmit }: AdminLoginFormProps) => {
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

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Input
              type="password"
              placeholder="Введите пароль"
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
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
};
