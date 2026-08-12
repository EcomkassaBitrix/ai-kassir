import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Save, X } from 'lucide-react';
import { EcomkassaSettingsSection } from '@/components/settings/EcomkassaSettingsSection';
import { useSettingsData } from '@/components/settings/useSettingsData';
import { TelegramLinkSection } from '@/components/settings/TelegramLinkSection';

const Settings = () => {
  const navigate = useNavigate();
  const {
    settings,
    isLoadingShops,
    loadShops,
    handleShopSelect,
    updateSettings,
    saveSettings
  } = useSettingsData();

  const handleSave = () => {
    saveSettings();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-purple-50 to-white p-4">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => navigate('/')}
        className="fixed top-8 right-14 text-gray-700 hover:bg-gray-100 hover:text-gray-900 z-50"
      >
        <X className="h-5 w-5" />
      </Button>
      
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/')}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold">Настройки Екомкасса</h1>
        </div>

        <div className="space-y-6">
          <EcomkassaSettingsSection
            settings={settings}
            isLoadingShops={isLoadingShops}
            onSettingsChange={updateSettings}
            onLoadShops={loadShops}
            onShopSelect={handleShopSelect}
          />

          <TelegramLinkSection />

          <Button onClick={handleSave} className="w-full">
            <Save className="mr-2 h-4 w-4" />
            Сохранить настройки
          </Button>

          <Button variant="outline" className="w-full" onClick={() => navigate('/api-docs')}>
            API документация
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Settings;