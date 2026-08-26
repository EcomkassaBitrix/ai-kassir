import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { useChatMessages } from '@/hooks/useChatMessages';
import { useReceiptState } from '@/hooks/useReceiptState';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useReceiptHandlers } from '@/hooks/useReceiptHandlers';
import { setEcomkassaLogin } from '@/utils/userId';
import { Shop } from '@/components/settings/types';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';

const PARTNER_EMBED_URL = 'https://functions.poehali.dev/10219b97-9c66-4c02-b8a3-939f2d6e06c6';

type EmbedStatus = 'loading' | 'select_shop' | 'ready' | 'error';

const Embed = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<EmbedStatus>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [shops, setShops] = useState<Shop[]>([]);
  const [isSelectingShop, setIsSelectingShop] = useState(false);
  const [input, setInput] = useState('');
  const [operationType, setOperationType] = useState('sell');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const { messages, setMessages } = useChatMessages();
  const embedTokenRef = useRef('');

  useEffect(() => {
    const token = searchParams.get('token');

    if (!token) {
      setStatus('error');
      setErrorMessage('Ссылка недействительна: отсутствует токен доступа');
      return;
    }

    embedTokenRef.current = token;

    const exchangeToken = async () => {
      try {
        const response = await fetch(PARTNER_EMBED_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'exchange', token })
        });

        const data = await response.json();

        if (!response.ok) {
          setStatus('error');
          setErrorMessage(data.error || 'Не удалось открыть чат');
          return;
        }

        if (data.ecomkassa_login) {
          setEcomkassaLogin(data.ecomkassa_login);
        }

        if (data.needs_shop_selection) {
          setShops(data.shops || []);
          setStatus('select_shop');
          return;
        }

        setStatus('ready');
      } catch (error) {
        setStatus('error');
        setErrorMessage('Ошибка соединения с сервером');
      }
    };

    exchangeToken();
  }, [searchParams]);

  const handleSelectShop = async (shopId: string) => {
    setIsSelectingShop(true);
    try {
      const response = await fetch(PARTNER_EMBED_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'select_shop', token: embedTokenRef.current, shop_id: shopId })
      });

      const data = await response.json();

      if (!response.ok) {
        setStatus('error');
        setErrorMessage(data.error || 'Не удалось выбрать магазин');
        return;
      }

      setStatus('ready');
    } catch (error) {
      setStatus('error');
      setErrorMessage('Ошибка соединения с сервером');
    } finally {
      setIsSelectingShop(false);
    }
  };

  const {
    pendingReceipt,
    setPendingReceipt,
    editMode,
    setEditMode,
    editedData,
    setEditedData,
    lastReceiptData,
    setLastReceiptData,
    updateEditedField
  } = useReceiptState();

  const { isListening, handleVoiceInput } = useVoiceInput(setInput);

  const {
    isProcessing,
    handleSendMessage: sendMessage,
    handleConfirmReceipt,
    handleCancelReceipt,
    handleEditToggle
  } = useReceiptHandlers(
    setMessages,
    pendingReceipt,
    setPendingReceipt,
    editedData,
    setEditedData,
    lastReceiptData,
    setLastReceiptData,
    setEditMode
  );

  const handleSendMessage = () => {
    sendMessage(input, operationType, setInput);
  };

  const handleRepeat = (messageContent: string) => {
    if (messageContent) {
      setInput(messageContent);
    }
  };

  useEffect(() => {
    if (status === 'ready') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, status]);

  if (status === 'loading') {
    return (
      <div className="h-screen bg-background flex flex-col items-center justify-center gap-3">
        <Icon name="Loader2" size={32} className="animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Загружаю чат...</p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="h-screen bg-background flex flex-col items-center justify-center gap-3 px-6 text-center">
        <Icon name="AlertCircle" size={32} className="text-destructive" />
        <p className="text-sm text-muted-foreground max-w-sm">{errorMessage}</p>
      </div>
    );
  }

  if (status === 'select_shop') {
    return (
      <div className="h-screen bg-background flex flex-col items-center justify-center gap-4 px-6">
        <Icon name="Store" size={28} className="text-primary" />
        <p className="text-sm text-muted-foreground text-center">Выберите магазин, в который будут отправляться чеки</p>
        <div className="w-full max-w-sm flex flex-col gap-2">
          {shops.map((shop) => (
            <Button
              key={shop.storeId}
              variant="outline"
              disabled={isSelectingShop}
              className="w-full justify-start h-auto py-3 text-left"
              onClick={() => handleSelectShop(shop.storeId)}
            >
              <div className="flex flex-col items-start gap-0.5">
                <span className="font-medium">{shop.storeName}</span>
                {shop.storeAddress && (
                  <span className="text-xs text-muted-foreground">{shop.storeAddress}</span>
                )}
              </div>
            </Button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-background flex flex-col">
      <div className="w-full h-full flex flex-col px-3 py-3 md:px-4 md:py-4">
        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto mb-3 space-y-4 overflow-x-hidden">
          {messages.map((message, index) => {
            const prevMessage = index > 0 ? messages[index - 1] : null;
            const userMessageContext = prevMessage?.type === 'user' ? prevMessage.content : undefined;

            return (
              <ChatMessage
                key={message.id}
                message={message}
                editedData={editedData}
                editMode={editMode}
                isProcessing={isProcessing}
                updateEditedField={updateEditedField}
                handleEditToggle={handleEditToggle}
                handleConfirmReceipt={handleConfirmReceipt}
                handleCancelReceipt={handleCancelReceipt}
                userMessage={userMessageContext}
                onRepeat={handleRepeat}
              />
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        <ChatInput
          input={input}
          setInput={setInput}
          isListening={isListening}
          isProcessing={isProcessing}
          operationType={operationType}
          setOperationType={setOperationType}
          handleSendMessage={handleSendMessage}
          handleVoiceInput={handleVoiceInput}
        />
      </div>
    </div>
  );
};

export default Embed;