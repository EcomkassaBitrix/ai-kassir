import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { AIProvider, AIModel } from './types';

interface TextRecognitionSectionProps {
  activeProvider: string;
  selectedModel: string | null;
  modelSelectMode: boolean;
  showGptunnelKeyInput: boolean;
  gptunnelApiKey: string;
  availableModels: AIModel[];
  textProviders: AIProvider[];
  activeTextProvider: AIProvider | undefined;
  setGptunnelApiKey: (key: string) => void;
  handleProviderChange: (providerId: string) => void;
  handleGptunnelKeySubmit: () => void;
  handleModelSelect: (modelId: string) => void;
  handleChangeModel: () => void;
  setShowGptunnelKeyInput: (show: boolean) => void;
  setModelSelectMode: (show: boolean) => void;
}

export const TextRecognitionSection = ({
  activeProvider,
  selectedModel,
  modelSelectMode,
  showGptunnelKeyInput,
  gptunnelApiKey,
  availableModels,
  textProviders,
  activeTextProvider,
  setGptunnelApiKey,
  handleProviderChange,
  handleGptunnelKeySubmit,
  handleModelSelect,
  handleChangeModel,
  setShowGptunnelKeyInput,
  setModelSelectMode
}: TextRecognitionSectionProps) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-4">
        <Icon name="MessageSquare" size={20} className="text-blue-400" />
        <h3 className="text-lg font-semibold text-white">Распознавание текста</h3>
      </div>
      
      {/* Форма ввода ключа GPTunnel */}
      {showGptunnelKeyInput && !modelSelectMode && (
        <div className="bg-blue-950/30 border border-blue-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-blue-400 mb-3">
            <Icon name="Key" size={16} />
            <span className="font-semibold">Введите API ключ GPTunnel</span>
          </div>
          <input
            type="text"
            value={gptunnelApiKey}
            onChange={(e) => setGptunnelApiKey(e.target.value)}
            placeholder="Bearer sk-..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-600 mb-3"
          />
          <div className="flex gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={handleGptunnelKeySubmit}
              className="flex-1"
            >
              Продолжить
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowGptunnelKeyInput(false)}
              className="text-gray-400 hover:text-white"
            >
              Отмена
            </Button>
          </div>
        </div>
      )}

      {/* Модальное окно выбора модели */}
      {modelSelectMode && !showGptunnelKeyInput && (
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
      {!modelSelectMode && !showGptunnelKeyInput && textProviders.map((provider) => {
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
  );
};
