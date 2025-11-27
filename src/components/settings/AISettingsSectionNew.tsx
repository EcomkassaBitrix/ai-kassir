import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import Icon from '@/components/ui/icon';

interface AIProvider {
  id: string;
  name: string;
  description: string;
  secret_name: string;
  has_secret: boolean;
}

interface AIModel {
  id: string;
  name: string;
  type: string;
}

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
  const [showKeyInput, setShowKeyInput] = useState(false);

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
        setYandexSpeechKitKey(''); // Очищаем ключ при отключении
        toast.success('Провайдер отключен');
        await loadSettings();
      }
      return;
    }
    
    if (providerId === 'gptunnel_chatgpt') {
      setTempProvider(providerId);
      setModelSelectMode(true);
      await loadSettings();
    } else if (providerId === 'yandex_speechkit') {
      // Всегда показываем форму ввода ключа
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
    const isValid = await validateKey(tempProvider, modelId);
    
    if (isValid) {
      setActiveProvider(tempProvider);
      setSelectedModel(modelId);
      setModelSelectMode(false);
      toast.success('Провайдер с моделью активирован ✓');
      await loadSettings();
    }
  };

  const handleChangeModel = async () => {
    setTempProvider('gptunnel_chatgpt');
    setModelSelectMode(true);
    await loadSettings(); // Загрузить модели
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
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-4">
            <Icon name="MessageSquare" size={20} className="text-blue-400" />
            <h3 className="text-lg font-semibold text-white">Распознавание текста</h3>
          </div>
          
          {/* Модальное окно выбора модели */}
          {modelSelectMode && (
          <div className="bg-blue-950/30 border border-blue-800 rounded-xl p-4">
            <div className="flex items-center gap-2 text-blue-400 mb-3">
              <Icon name="Sparkles" size={16} />
              <span className="font-semibold">Выберите модель для GPTunnel</span>
            </div>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {availableModels.length > 0 ? (
                availableModels.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => handleModelSelect(model.id)}
                    className="w-full flex items-center justify-between p-3 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-blue-600 transition-all text-left"
                  >
                    <div>
                      <div className="font-medium text-white">{model.name}</div>
                      <div className="text-xs text-gray-400">{model.id}</div>
                    </div>
                    <span className="text-xs bg-blue-900 text-blue-300 px-2 py-1 rounded">
                      {model.type}
                    </span>
                  </button>
                ))
              ) : (
                <div className="text-center py-4 text-gray-500">
                  Загрузка моделей...
                </div>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setModelSelectMode(false)}
              className="mt-3 w-full text-gray-400 hover:text-white"
            >
              Отмена
            </Button>
          </div>
        )}

        {/* Активный провайдер текста */}
        {activeTextProvider && !modelSelectMode && (
          <div className="bg-green-950/20 border border-green-800/50 rounded-xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Icon name="Check" size={20} className="text-green-500" />
              <div>
                <div className="text-green-400 font-semibold">
                  Подключен: {activeTextProvider.name}
                </div>
                {selectedModel && (
                  <div className="text-xs text-green-600 mt-0.5">
                    Модель: {selectedModel}
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              {activeTextProvider.id === 'gptunnel_chatgpt' && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleChangeModel}
                  className="bg-transparent border-blue-700 text-blue-400 hover:bg-blue-950/30"
                >
                  Сменить модель
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleProviderChange('')}
                className="bg-transparent border-red-800 text-red-400 hover:bg-red-950/30 hover:text-red-300"
              >
                Отключить
              </Button>
            </div>
          </div>
        )}

        {/* Список провайдеров текста */}
        {!modelSelectMode && textProviders.map((provider) => {
          const isActive = activeProvider === provider.id;
          if (isActive) return null;

          return (
            <div
              key={provider.id}
              className="bg-green-950/10 border border-green-800/30 rounded-xl p-4 flex items-center justify-between"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white">{provider.name}</h3>
                  <span className="text-xs bg-green-900/50 text-green-400 px-2 py-0.5 rounded-full">
                    Активно
                  </span>
                </div>
                <p className="text-sm text-green-600 mt-1">{provider.description}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleProviderChange(provider.id)}
                disabled={!provider.has_secret}
                className="bg-transparent border-green-700 text-green-400 hover:bg-green-950/30"
              >
                Активировать
              </Button>
            </div>
          );
        })}
        </div>

        {/* Раздел 2: Распознавание голоса */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-4">
            <Icon name="Mic" size={20} className="text-purple-400" />
            <h3 className="text-lg font-semibold text-white">Распознавание голоса</h3>
          </div>

        {/* Активный провайдер голоса */}
        {activeSpeechProvider && !modelSelectMode && (
          <div className="bg-green-950/20 border border-green-800/50 rounded-xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Icon name="Check" size={20} className="text-green-500" />
              <div>
                <div className="text-green-400 font-semibold">
                  Подключен: {activeSpeechProvider.name}
                </div>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleProviderChange('')}
              className="bg-transparent border-red-800 text-red-400 hover:bg-red-950/30 hover:text-red-300"
            >
              Отключить
            </Button>
          </div>
        )}

        {/* Форма ввода ключа Yandex SpeechKit */}
        {showKeyInput && !modelSelectMode && (
          <div className="bg-blue-950/30 border border-blue-800 rounded-xl p-4">
            <div className="flex items-center gap-2 text-blue-400 mb-3">
              <Icon name="Key" size={16} />
              <span className="font-semibold">Введите API ключ Yandex SpeechKit</span>
            </div>
            <input
              type="text"
              value={yandexSpeechKitKey}
              onChange={(e) => setYandexSpeechKitKey(e.target.value)}
              placeholder="AQVNxxxxxxxxxx..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-600 mb-3"
            />
            <div className="flex gap-2">
              <Button
                variant="default"
                size="sm"
                onClick={handleSpeechKitActivate}
                className="flex-1"
              >
                Активировать
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowKeyInput(false)}
                className="text-gray-400 hover:text-white"
              >
                Отмена
              </Button>
            </div>
          </div>
        )}

        {/* Список провайдеров голоса */}
        {!modelSelectMode && !showKeyInput && speechProviders.map((provider) => {
          const isActive = activeProvider === provider.id;
          if (isActive) return null;

          return (
            <div
              key={provider.id}
              className="bg-gray-900 border border-gray-700 rounded-xl p-4 flex items-center justify-between"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white">{provider.name}</h3>
                </div>
                <p className="text-sm text-gray-400 mt-1">{provider.description}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleProviderChange(provider.id)}
                className="bg-transparent border-gray-600 text-gray-300 hover:bg-gray-800"
              >
                Настроить
              </Button>
            </div>
          );
        })}
        </div>

      </CardContent>
    </Card>
  );
};