import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Message } from '@/types/message';
import { sendReceiptPreview, confirmReceipt } from '@/services/receiptApi';

const OPERATION_NAMES: Record<string, string> = {
  sell: 'Продажа',
  refund: 'Возврат',
  sell_correction: 'Коррекция прихода',
  refund_correction: 'Коррекция расхода'
};

export const useReceiptHandlers = (
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  pendingReceipt: any,
  setPendingReceipt: (value: any) => void,
  editedData: any,
  setEditedData: (value: any) => void,
  lastReceiptData: any,
  setLastReceiptData: (value: any) => void,
  setEditMode: (value: boolean) => void
) => {
  const navigate = useNavigate();
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSendMessage = async (input: string, operationType: string, setInput: (value: string) => void) => {
    if (!input.trim() || isProcessing) return;
    
    const clearCommands = ['очисти историю', 'почисти историю', 'очистить историю', 'почистить историю', 'очисти', 'почисти'];
    if (clearCommands.some(cmd => input.toLowerCase().trim() === cmd)) {
      setMessages((prev) => {
        const initialMsg = prev.find(m => m.id === '1');
        return initialMsg ? [initialMsg] : [];
      });
      localStorage.removeItem('chat_messages');
      setInput('');
      toast.success('История переписки очищена');
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const userInput = input;
    setInput('');
    setIsProcessing(true);
    
    const processingMessage: Message = {
      id: (Date.now() + 1).toString(),
      type: 'agent',
      content: 'Работаю, минуту...',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, processingMessage]);
    
    setPendingReceipt(null);
    setEditMode(false);
    setEditedData(null);

    try {
      const savedSettings = localStorage.getItem('ecomkassa_settings');
      const settings = savedSettings ? JSON.parse(savedSettings) : {};
      
      const contextMessage = localStorage.getItem('context_message') || '';
      settings.context_message = contextMessage;
      
      const data = await sendReceiptPreview(userInput, operationType, settings, lastReceiptData);

      if (data.error) {
        const currentContext = localStorage.getItem('context_message') || '';
        const updatedContext = currentContext ? `${currentContext} ${userInput}` : userInput;
        localStorage.setItem('context_message', updatedContext);
        
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'agent',
          content: `❌ ${data.message || data.error}`,
          timestamp: new Date(),
        };
        setMessages((prev) => {
          const filtered = prev.filter(m => m.content !== 'Работаю, минуту...');
          return [...filtered, errorMessage];
        });
        
        if (data.missing_integration) {
          toast.error(data.error, {
            action: {
              label: 'Настройки',
              onClick: () => navigate('/settings')
            }
          });
        } else if (data.missing_field === 'email') {
          toast.error('Не указан email', {
            action: {
              label: 'Настройки',
              onClick: () => navigate('/settings')
            }
          });
        } else {
          toast.error(data.error);
        }
        return;
      }

      const detectedType = data.operation_type || operationType;
      const typeName = OPERATION_NAMES[detectedType] || detectedType;

      const previewMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'preview',
        content: 'Проверь данные чека перед отправкой',
        timestamp: new Date(),
        previewData: { ...data.receipt, operation_type: detectedType, typeName },
      };

      localStorage.removeItem('context_message');
      
      setMessages((prev) => {
        const filtered = prev.filter(m => m.content !== 'Работаю, минуту...' && m.type !== 'preview');
        return [...filtered, previewMessage];
      });
      setPendingReceipt({ userInput, operationType: detectedType });
      setEditedData({ ...data.receipt, operation_type: detectedType, typeName });
      setLastReceiptData(data.receipt);
      toast.info('Проверь данные и подтверди отправку');
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 2).toString(),
        type: 'agent',
        content: 'Произошла ошибка при обработке запроса. Попробуй еще раз.',
        timestamp: new Date(),
      };
      setMessages((prev) => {
        const filtered = prev.filter(m => m.content !== 'Работаю, минуту...');
        return [...filtered, errorMessage];
      });
      toast.error('Ошибка соединения с сервером');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleConfirmReceipt = async () => {
    if (!pendingReceipt) return;
    
    setIsProcessing(true);
    
    const processingMessageId = Date.now().toString();
    const processingMessage: Message = {
      id: processingMessageId,
      type: 'agent',
      content: 'Отправляю чек...',
      timestamp: new Date(),
    };
    setMessages((prev) => {
      const filtered = prev.filter(m => m.type !== 'preview');
      return [...filtered, processingMessage];
    });
    
    try {
      const savedSettings = localStorage.getItem('ecomkassa_settings');
      const settings = savedSettings ? JSON.parse(savedSettings) : {};
      
      const data = await confirmReceipt(
        pendingReceipt.userInput,
        pendingReceipt.operationType,
        editedData,
        lastReceiptData,
        settings
      );

      const typeName = OPERATION_NAMES[pendingReceipt.operationType] || pendingReceipt.operationType;
      const messageContent = data.success 
        ? (data.message || 'Чек успешно отправлен в ЕкомКасса') 
        : `Ошибка: ${data.message || data.error || 'Неизвестная ошибка'}`;
      
      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'agent',
        content: messageContent,
        timestamp: new Date(),
        receiptData: data.success ? data.receipt : null,
        receiptUuid: data.uuid,
        receiptPermalink: data.permalink,
        hasError: !data.success,
        errorMessage: !data.success ? (data.message || data.error || 'Неизвестная ошибка') : undefined,
      };

      setMessages((prev) => {
        const filtered = prev.filter(m => m.id !== processingMessageId);
        return [...filtered, agentMessage];
      });
      setPendingReceipt(null);
      setEditMode(false);
      setEditedData(null);
      setLastReceiptData(null);
      localStorage.removeItem('context_message');
      
      if (data.success) {
        toast.success(`Чек успешно создан! Тип: ${typeName}`);
      } else {
        toast.error('Произошла ошибка при создании чека');
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 2).toString(),
        type: 'agent',
        content: 'Ошибка соединения с сервером. Попробуй еще раз.',
        timestamp: new Date(),
        hasError: true,
      };
      setMessages((prev) => {
        const filtered = prev.filter(m => m.id !== processingMessageId);
        return [...filtered, errorMessage];
      });
      toast.error('Ошибка соединения с сервером');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCancelReceipt = () => {
    setMessages((prev) => {
      const filtered = prev.filter(m => m.type !== 'preview');
      const cancelMessage: Message = {
        id: Date.now().toString(),
        type: 'agent',
        content: 'Проверка данных чека отменена',
        timestamp: new Date(),
      };
      return [...filtered, cancelMessage];
    });
    setPendingReceipt(null);
    setEditMode(false);
    setEditedData(null);
    setLastReceiptData(null);
    localStorage.removeItem('context_message');
    toast.info('Отменено');
  };

  const handleEditToggle = () => {
    setEditMode((prev) => !prev);
  };

  return {
    isProcessing,
    handleSendMessage,
    handleConfirmReceipt,
    handleCancelReceipt,
    handleEditToggle
  };
};