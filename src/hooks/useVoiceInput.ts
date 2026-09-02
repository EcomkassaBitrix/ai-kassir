import { useState } from 'react';
import { toast } from 'sonner';

export const useVoiceInput = (setInput: (value: string) => void) => {
  const [isListening, setIsListening] = useState(false);

  const handleVoiceInput = async () => {
    if (!('webkitSpeechRecognition' in window)) {
      toast.error('Голосовой ввод не поддерживается в вашем браузере');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
    } catch (error: any) {
      console.error('Microphone permission error:', error);
      if (error.name === 'NotAllowedError') {
        toast.error('Доступ к микрофону запрещён. В Safari: Настройки → Веб-сайты → Микрофон. Если не поможет — macOS: Системные настройки → Конфиденциальность и безопасность → Распознавание речи → включите Safari');
      } else if (error.name === 'NotFoundError') {
        toast.error('Микрофон не найден. Подключите микрофон к устройству');
      } else {
        toast.error('Не удалось получить доступ к микрофону');
      }
      return;
    }

    const recognition = new (window as any).webkitSpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setIsListening(true);
      toast.info('Говорите...');
    };

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      setIsListening(false);
      toast.success('Распознано');
    };

    recognition.onerror = (event: any) => {
      setIsListening(false);
      console.error('Speech recognition error:', event.error, event);
      
      if (event.error === 'not-allowed') {
        toast.error('Доступ к микрофону запрещен. Откройте Настройки Safari → Веб-сайты → Микрофон');
      } else if (event.error === 'no-speech') {
        toast.error('Речь не обнаружена. Попробуйте еще раз');
      } else if (event.error === 'network') {
        toast.error('Ошибка сети. Проверьте подключение к интернету');
      } else {
        toast.error(`Ошибка распознавания: ${event.error}`);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    try {
      recognition.start();
    } catch (error) {
      setIsListening(false);
      console.error('Failed to start recognition:', error);
      toast.error('Не удалось запустить распознавание речи');
    }
  };

  return { isListening, handleVoiceInput };
};