import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { AIProvider } from './types';

interface VoiceRecognitionSectionProps {
  activeProvider: string;
  showKeyInput: boolean;
  yandexSpeechKitKey: string;
  speechProviders: AIProvider[];
  activeSpeechProvider: AIProvider | undefined;
  modelSelectMode: boolean;
  setYandexSpeechKitKey: (key: string) => void;
  handleProviderChange: (providerId: string) => void;
  handleSpeechKitActivate: () => void;
  setShowKeyInput: (show: boolean) => void;
}

export const VoiceRecognitionSection = ({
  activeProvider,
  showKeyInput,
  yandexSpeechKitKey,
  speechProviders,
  activeSpeechProvider,
  modelSelectMode,
  setYandexSpeechKitKey,
  handleProviderChange,
  handleSpeechKitActivate,
  setShowKeyInput
}: VoiceRecognitionSectionProps) => {
  return (
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
  );
};
