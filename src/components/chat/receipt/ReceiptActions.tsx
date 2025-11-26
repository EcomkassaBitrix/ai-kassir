import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from '@/components/ui/icon';

interface ReceiptActionsProps {
  editedData: any;
  editMode: boolean;
  isProcessing: boolean;
  updateEditedField: (path: string, value: any) => void;
  handleEditToggle: () => void;
  handleConfirmReceipt: () => void;
  handleCancelReceipt: () => void;
}

export const ReceiptActions = ({
  editedData,
  editMode,
  isProcessing,
  updateEditedField,
  handleEditToggle,
  handleConfirmReceipt,
  handleCancelReceipt,
}: ReceiptActionsProps) => {
  const isBulkMode = editedData.bulk_count && editedData.original_uuid;

  return (
    <>
      <div className="bg-background/50 p-3 rounded space-y-2">
        <div className="flex justify-between items-center mb-2">
          <div className="text-xs font-medium text-muted-foreground">Способы оплаты</div>
          {editMode && (
            <Button
              onClick={() => {
                const newPayments = [...(editedData.payments || []), { type: '1', sum: 0 }];
                updateEditedField('payments', newPayments);
              }}
              variant="outline"
              size="sm"
              className="h-6 text-xs"
            >
              <Icon name="Plus" size={12} className="mr-1" />
              Добавить
            </Button>
          )}
        </div>
        {editedData.payments?.map((payment: any, idx: number) => {
          const paymentNames: Record<string, string> = {
            '0': 'Наличные',
            '1': 'Безналичный',
            '2': 'Предоплата (аванс)',
            '3': 'Последующая оплата (кредит)',
            '4': 'Иная форма',
            '5': 'Расширенный аванс',
            '6': 'Расширенный кредит'
          };
          
          return (
            <div key={idx} className="flex gap-2 items-center pb-2 border-b border-border/50 last:border-0">
              {editMode ? (
                <>
                  <select
                    value={payment.type}
                    onChange={(e) => {
                      const newPayments = [...editedData.payments];
                      newPayments[idx].type = e.target.value;
                      updateEditedField('payments', newPayments);
                    }}
                    className="flex-1 h-7 text-sm bg-background border rounded px-2"
                  >
                    <option value="0">Наличные</option>
                    <option value="1">Безналичный</option>
                    <option value="2">Предоплата (аванс)</option>
                    <option value="3">Последующая оплата (кредит)</option>
                    <option value="4">Иная форма оплаты</option>
                    <option value="5">Расширенный аванс</option>
                    <option value="6">Расширенный кредит</option>
                  </select>
                  <Input
                    type="number"
                    value={payment.sum || 0}
                    onChange={(e) => {
                      const newPayments = [...editedData.payments];
                      newPayments[idx].sum = parseFloat(e.target.value) || 0;
                      updateEditedField('payments', newPayments);
                    }}
                    className="w-24 h-7 text-sm"
                    placeholder="Сумма"
                  />
                  {editedData.payments.length > 1 && (
                    <Button
                      onClick={() => {
                        const newPayments = editedData.payments.filter((_: any, i: number) => i !== idx);
                        updateEditedField('payments', newPayments);
                      }}
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                    >
                      <Icon name="Trash2" size={14} />
                    </Button>
                  )}
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm">{paymentNames[payment.type] || 'Безналичный'}</span>
                  <span className="text-sm font-medium">{payment.sum || 0}₽</span>
                </>
              )}
            </div>
          );
        })}
        {(() => {
          const paymentsTotal = editedData.payments?.reduce((sum: number, p: any) => sum + (parseFloat(p.sum) || 0), 0) || 0;
          const itemsTotal = editedData.total || 0;
          const isValid = Math.abs(paymentsTotal - itemsTotal) < 0.01;
          
          return (
            <div className={`flex justify-between text-sm font-bold pt-2 border-t border-border ${!isValid && editMode ? 'text-destructive' : ''}`}>
              <span>Сумма платежей</span>
              <span>{paymentsTotal.toFixed(2)}₽ {!isValid && editMode && '⚠️'}</span>
            </div>
          );
        })()}
      </div>
    </>
  );
};