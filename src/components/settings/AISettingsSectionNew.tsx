import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { AIProvider, AIModel } from './ai-settings/types';
import { TextRecognitionSection } from './ai-settings/TextRecognitionSection';
import { VoiceRecognitionSection } from './ai-settings/VoiceRecognitionSection';

interface AISettingsSectionNewProps {
  adminToken: string;
}

export const AISettingsSectionNew = ({ adminToken }: AISettingsSectionNewProps) => {
  const [activeProvider, setActiveProvider] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<AIModel[]>([]);
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [modelSelectMode, setModelSelectMode] = useState(false);
  const [tempProvider, setTempProvider] = useState<string>('');
  const [yandexSpeechKitKey, setYandexSpeechKitKey] = useState<string>('');
  const [gptunnelApiKey, setGptunnelApiKey] = useState<string>('');
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [showGptunnelKeyInput, setShowGptunnelKeyInput] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await fetch('https://functions.poehali.dev/0924c3f7-bb48-46bb-9dbb-fddba37c9280', {
        headers: {
          'X-Admin-Token': adminToken
        }
      });

      if (!response.ok) {
        throw new Error('Failed to load settings');
      }

      const data = await response.json();
      setActiveProvider(data.active_provider || '');
      setSelectedModel(data.selected_model || null);
      setAvailableModels(data.available_models || []);
      setProviders(data.available_providers || []);
      setYandexSpeechKitKey(data.yandex_speechkit_key || '');
      setGptunnelApiKey(data.gptunnel_api_key || '');
    } catch (error) {
      toast.error('Ошибка загрузки настроек ИИ');
    } finally {
      setLoading(false);
    }
  };

  const validateKey = async (providerId: string, modelId?: string, speechKitKey?: string) => {
    const validatingToast = toast.loading('Проверяю API ключ...');
    
    try {
      const body: any = { 
        provider_id: providerId,
        selected_model: modelId 
      };
      
      if (providerId === 'yandex_speechkit' && speechKitKey) {
        body.yandex_speechkit_key = speechKitKey;
      }
      
      if (providerId === 'gptunnel_chatgpt' && gptunnelApiKey) {
        body.gptunnel_api_key = gptunnelApiKey;
      }
      
      const response = await fetch('https://functions.poehali.dev/0924c3f7-bb48-46bb-9dbb-fddba37c9280', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': adminToken
        },
        body: JSON.stringify(body)
      });

      const data = await response.json();
      toast.dismiss(validatingToast);

      if (!response.ok) {
        toast.error(data.message || data.error || 'Ключ невалиден');
        return false;
      }

      toast.success('Ключ валиден ✓');
      return true;
    } catch (error) {
      toast.dismiss(validatingToast);
      toast.error('Ошибка подключения');
      return false;
    }
  };

  const handleProviderChange = async (providerId: string) => {
    if (!providerId) {
      const isValid = await validateKey('');
      if (isValid) {
        setActiveProvider('');
        setSelectedModel(null);
        setYandexSpeechKitKey('');
        setGptunnelApiKey('');
        toast.success('Провайдер отключен');
        await loadSettings();
      }
      return;
    }
    
    if (providerId === 'gptunnel_chatgpt') {
      setShowGptunnelKeyInput(true);
    } else if (providerId === 'yandex_speechkit') {
      setShowKeyInput(true);
    } else {
      const isValid = await validateKey(providerId);
      
      if (isValid) {
        setActiveProvider(providerId);
        setSelectedModel(null);
        toast.success('Провайдер активирован ✓');
        await loadSettings();
      }
    }
  };

  const handleModelSelect = async (modelId: string) => {
    const validatingToast = toast.loading('Активирую провайдер...');
    
    try {
      const response = await fetch('https://functions.poehali.dev/0924c3f7-bb48-46bb-9dbb-fddba37c9280', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': adminToken
        },
        body: JSON.stringify({
          provider_id: tempProvider,
          selected_model: modelId,
          gptunnel_api_key: gptunnelApiKey
        })
      });

      const data = await response.json();
      toast.dismiss(validatingToast);

      if (!response.ok) {
        toast.error(data.message || data.error || 'Ошибка активации');
        return;
      }

      setActiveProvider(tempProvider);
      setSelectedModel(modelId);
      setModelSelectMode(false);
      toast.success('Провайдер с моделью активирован ✓');
      await loadSettings();
    } catch (error) {
      toast.dismiss(validatingToast);
      toast.error('Ошибка подключения');
    }
  };

  const handleChangeModel = async () => {
    setTempProvider('gptunnel_chatgpt');
    setModelSelectMode(true);
    await loadSettings();
  };

  const handleGptunnelKeySubmit = async () => {
    if (!gptunnelApiKey.trim()) {
      toast.error('Введите API ключ GPTunnel');
      return;
    }
    
    const validatingToast = toast.loading('Проверяю API ключ...');
    
    try {
      const response = await fetch('https://gptunnel.ru/v1/models', {
        headers: {'Authorization': gptunnelApiKey},
        timeout: 15000
      });
      
      toast.dismiss(validatingToast);
      
      if (!response.ok) {
        toast.error('Невалидный API ключ GPTunnel');
        return;
      }
      
      const data = await response.json();
      const models = data.data?.map((m: any) => ({
        id: m.id,
        name: m.title || m.id,
        type: m.type || 'TEXT'
      })) || [];
      
      if (models.length === 0) {
        toast.error('Не удалось загрузить модели');
        return;
      }
      
      setAvailableModels(models);
      setShowGptunnelKeyInput(false);
      setTempProvider('gptunnel_chatgpt');
      setModelSelectMode(true);
      toast.success('Ключ валиден ✓');
    } catch (error) {
      toast.dismiss(validatingToast);
      toast.error('Ошибка подключения');
    }
  };

  const handleSpeechKitActivate = async () => {
    if (!yandexSpeechKitKey.trim()) {
      toast.error('Введите API ключ Yandex SpeechKit');
      return;
    }
    
    const isValid = await validateKey('yandex_speechkit', undefined, yandexSpeechKitKey);
    
    if (isValid) {
      setActiveProvider('yandex_speechkit');
      setShowKeyInput(false);
      toast.success('Yandex SpeechKit активирован ✓');
      await loadSettings();
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto"></div>
        </CardContent>
      </Card>
    );
  }

  const textProviders = providers.filter(p => p.id !== 'yandex_speechkit' && p.id !== 'gigachat');
  const speechProviders = providers.filter(p => p.id === 'yandex_speechkit');
  
  const activeTextProvider = textProviders.find(p => p.id === activeProvider);
  const activeSpeechProvider = speechProviders.find(p => p.id === activeProvider);

  return (
    <Card className="bg-[#1a1a1a] border-gray-800">
      <CardHeader>
        <CardTitle className="text-white">Настройки ИИ-провайдера</CardTitle>
        <CardDescription className="text-gray-400">
          Выберите активного провайдера для обработки запросов. API-ключи хранятся в секретах проекта.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        
        {/* Раздел 1: Распознавание текста */}
        <TextRecognitionSection
          activeProvider={activeProvider}
          selectedModel={selectedModel}
          modelSelectMode={modelSelectMode}
          showGptunnelKeyInput={showGptunnelKeyInput}
          gptunnelApiKey={gptunnelApiKey}
          availableModels={availableModels}
          textProviders={textProviders}
          activeTextProvider={activeTextProvider}
          setGptunnelApiKey={setGptunnelApiKey}
          handleProviderChange={handleProviderChange}
          handleGptunnelKeySubmit={handleGptunnelKeySubmit}
          handleModelSelect={handleModelSelect}
          handleChangeModel={handleChangeModel}
          setShowGptunnelKeyInput={setShowGptunnelKeyInput}
          setModelSelectMode={setModelSelectMode}
        />

        {/* Раздел 2: Распознавание голоса */}
        <VoiceRecognitionSection
          activeProvider={activeProvider}
          showKeyInput={showKeyInput}
          yandexSpeechKitKey={yandexSpeechKitKey}
          speechProviders={speechProviders}
          activeSpeechProvider={activeSpeechProvider}
          modelSelectMode={modelSelectMode}
          setYandexSpeechKitKey={setYandexSpeechKitKey}
          handleProviderChange={handleProviderChange}
          handleSpeechKitActivate={handleSpeechKitActivate}
          setShowKeyInput={setShowKeyInput}
        />

      </CardContent>
    </Card>
  );
};
