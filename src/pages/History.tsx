import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

interface Receipt {
  id: number;
  external_id: string;
  user_message: string;
  operation_type: string;
  items: Array<{ name: string; price: number; quantity: number }>;
  total: number;
  payment_type: string;
  status: string;
  demo_mode: boolean;
  created_at: string;
  uuid?: string;
}

interface HistoryProps {
  setRepeatCommand: (value: string) => void;
}

const History = ({ setRepeatCommand }: HistoryProps) => {
  const navigate = useNavigate();
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchReceipts();
  }, []);

  const fetchReceipts = async () => {
    try {
      const userId = localStorage.getItem('poehali_user_id') || '';
      const response = await fetch('https://functions.poehali.dev/1e30d22a-a25c-46a5-b05a-ccc647ed9bb6', {
        headers: {
          'X-User-Id': userId
        }
      });
      const data = await response.json();

      if (data.success) {
        setReceipts(data.receipts);
        setTotal(data.total);
      } else {
        toast.error('Ошибка загрузки истории');
      }
    } catch (error) {
      toast.error('Не удалось загрузить историю');
    } finally {
      setLoading(false);
    }
  };

  const getOperationTypeName = (type: string) => {
    const types: Record<string, string> = {
      sell: 'Продажа товаров/услуг',
      refund: 'Возврат средств',
      sell_correction: 'Коррекция прихода',
      refund_correction: 'Коррекция расхода',
    };
    return types[type] || type;
  };

  const getPaymentTypeName = (type: string, receipt?: Receipt) => {
    // Если есть несколько типов оплаты, проверяем payments
    if (receipt && typeof receipt.payment_type === 'string' && receipt.payment_type.includes(',')) {
      const types = receipt.payment_type.split(',').map(t => t.trim());
      const uniqueTypes = [...new Set(types)];
      
      if (uniqueTypes.length > 1) {
        const names = uniqueTypes.map(t => {
          const typeNames: Record<string, string> = {
            '0': 'Наличные',
            '1': 'Безнал',
            '2': 'Предоплата',
            '3': 'Кредит',
            '4': 'Встречное',
          };
          return typeNames[t] || t;
        });
        return names.join(' + ');
      }
    }
    
    const types: Record<string, string> = {
      '0': 'Наличные',
      '1': 'Безналичный',
      '2': 'Предоплата',
      '3': 'Кредит',
      '4': 'Встречное предоставление',
      'cash': 'Наличные',
      'card': 'Безналичный',
      'electronically': 'Безналичный',
    };
    return types[type] || 'Безналичный';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-purple-950/20">
      <div className="container max-w-5xl mx-auto p-6">
        <header className="flex items-center justify-between mb-8 pt-4">
          <div className="flex items-center gap-3">
            <Button variant="outline" size="icon" className="rounded-xl" onClick={() => navigate('/')}>
              <Icon name="ArrowLeft" size={20} />
            </Button>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                История чеков
              </h1>
              <p className="text-sm text-muted-foreground">Всего чеков: {total}</p>
            </div>
          </div>
        </header>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-3">
              <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              <p className="text-muted-foreground">Загрузка истории...</p>
            </div>
          </div>
        ) : receipts.length === 0 ? (
          <Card className="p-12 text-center">
            <Icon name="FileText" size={48} className="mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">История пуста</h3>
            <p className="text-muted-foreground mb-6">Создай первый чек, чтобы увидеть его здесь</p>
            <Button onClick={() => navigate('/')} className="bg-gradient-to-r from-primary to-secondary">
              <Icon name="Plus" size={20} className="mr-2" />
              Создать чек
            </Button>
          </Card>
        ) : (
          <div className="space-y-4">
            {receipts.map((receipt) => (
              <Card key={receipt.id} className="p-6 hover:border-primary/40 transition-colors">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant={receipt.demo_mode ? 'secondary' : 'default'}>
                        {receipt.demo_mode ? 'Демо' : 'Екомкасса'}
                      </Badge>
                      <Badge variant="outline">{getOperationTypeName(receipt.operation_type)}</Badge>
                    </div>
                    {receipt.uuid && (
                      <p className="text-sm mb-1">
                        <span className="text-muted-foreground">Чек </span>
                        <a
                          href={`https://app.ecomkassa.ru/admin/orders/${receipt.uuid}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline font-mono text-xs"
                        >
                          {receipt.uuid}
                        </a>
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {new Date(receipt.created_at).toLocaleString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                      {receipt.total}₽
                    </div>
                    <div className="text-xs text-muted-foreground">{getPaymentTypeName(receipt.payment_type, receipt)}</div>
                    {receipt.uuid && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-1"
                        onClick={() => {
                          setRepeatCommand(`повтори чек ${receipt.uuid}`);
                          navigate('/');
                        }}
                      >
                        <Icon name="RotateCw" size={14} className="mr-1" />
                        Повторить
                      </Button>
                    )}
                  </div>
                </div>

                <div className="border-t border-primary/20 pt-4 space-y-2">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                    <Icon name="Package" size={14} />
                    <span>Товары:</span>
                  </div>
                  {receipt.items.map((item, idx) => (
                    <div key={idx} className="flex justify-between text-sm">
                      <span>
                        {item.name} x{item.quantity}
                      </span>
                      <span className="text-muted-foreground">{item.price}₽</span>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default History;