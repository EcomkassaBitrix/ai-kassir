import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { IntegrationSettings, AIProvider, Shop } from './types';
import { getUserId, setEcomkassaLogin } from '@/utils/userId';

export const useSettingsData = () => {
  const [settings, setSettings] = useState<IntegrationSettings>({
    group_code: '',
    inn: '',
    sno: 'usn_income',
    default_vat: 'none',
    company_email: '',
    payment_address: '',
    active_ai_provider: '',
    gigachat_auth_key: '',
    yandexgpt_api_key: '',
    yandexgpt_folder_id: '',
    gptunnel_api_key: '',
    ecomkassa_login: '',
    ecomkassa_password: '',
    available_shops: []
  });
  const [isLoadingShops, setIsLoadingShops] = useState(false);

  const aiProviders: AIProvider[] = [
    {
      id: 'gigachat',
      name: 'GigaChat (Сбер)',
      description: 'Российская модель от Сбера',
      apiKeyLabel: 'Authorization Key',
      apiKeyPlaceholder: 'base64(Client_ID:Client_Secret)',
      docsUrl: 'https://developers.sber.ru/studio/workspaces',
      isActive: !!settings.gigachat_auth_key
    },
    {
      id: 'yandexgpt',
      name: 'YandexGPT',
      description: 'Российская модель от Яндекса',
      apiKeyLabel: 'YandexGPT API Key',
      apiKeyPlaceholder: 'AQVNxxxxxx...',
      docsUrl: 'https://cloud.yandex.ru/docs/yandexgpt',
      isActive: !!settings.yandexgpt_api_key && !!settings.yandexgpt_folder_id
    },
    {
      id: 'gptunnel_chatgpt',
      name: 'ChatGPT (GPT Tunnel)',
      description: 'GPT-4o через российский сервис',
      apiKeyLabel: 'GPT Tunnel API Key',
      apiKeyPlaceholder: 'gt-xxxxxx...',
      docsUrl: 'https://gptunnel.ru/',
      isActive: !!settings.gptunnel_api_key
    },
    {
      id: 'gptunnel_claude',
      name: 'Claude 3.5 Sonnet (GPT Tunnel)',
      description: 'Claude 3.5 через российский сервис',
      apiKeyLabel: 'GPT Tunnel API Key',
      apiKeyPlaceholder: 'gt-xxxxxx...',
      docsUrl: 'https://gptunnel.ru/',
      isActive: !!settings.gptunnel_api_key
    }
  ];

  useEffect(() => {
    loadSettingsFromServer();
  }, []);

  const loadSettingsFromServer = async () => {
    const userId = getUserId();
    
    try {
      const response = await fetch('https://functions.poehali.dev/e8972b95-5a58-4023-8f81-5385338d4590', {
        headers: {
          'X-User-Id': userId
        }
      });

      if (!response.ok) {
        throw new Error('Failed to load settings');
      }

      const data = await response.json();
      const serverSettings = data.settings || {};

      setSettings({
        group_code: serverSettings.group_code || '',
        inn: serverSettings.inn || '',
        sno: serverSettings.sno || 'usn_income',
        default_vat: serverSettings.default_vat || 'none',
        company_email: serverSettings.company_email || '',
        payment_address: serverSettings.payment_address || '',
        ecomkassa_login: serverSettings.ecomkassa_login || '',
        ecomkassa_password: serverSettings.ecomkassa_password || '',
        active_ai_provider: serverSettings.active_ai_provider || '',
        gigachat_auth_key: serverSettings.gigachat_auth_key || '',
        yandexgpt_api_key: serverSettings.yandexgpt_api_key || '',
        yandexgpt_folder_id: serverSettings.yandexgpt_folder_id || '',
        gptunnel_api_key: serverSettings.gptunnel_api_key || '',
        available_shops: []
      });
    } catch (error) {
      console.error('[Settings] Failed to load from server:', error);
      toast.error('Ошибка загрузки настроек с сервера');
    }
  };

  const loadShops = async () => {
    if (!settings.ecomkassa_login || !settings.ecomkassa_password) {
      toast.error('Введите логин и пароль API Екомкасса');
      return;
    }

    setIsLoadingShops(true);
    try {
      const response = await fetch('https://functions.poehali.dev/43959fb6-01cc-48d6-83ce-8160cf016d09', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          login: settings.ecomkassa_login,
          password: settings.ecomkassa_password,
          endpoint: '/api/mobile/v1/profile/firm'
        })
      });

      const data = await response.json();

      if (!response.ok) {
        const errorMsg = data.error || `Ошибка ${response.status}`;
        toast.error(`API Екомкасса: ${errorMsg}`);
        return;
      }

      if (typeof data === 'string') {
        toast.error('API вернул некорректные данные. Проверьте логин и пароль.');
        return;
      }

      if (data.errorCode !== 0) {
        toast.error(`API Екомкасса: ${data.error || 'Неизвестная ошибка'}`);
        return;
      }

      const payload = data.payload || {};
      const taxIdentity = payload.taxIdentity || '';
      const taxVariant = payload.taxVariant || 'usn_income';
      const stores = payload.stores || [];

      const shops: Shop[] = stores.map((shop: any) => ({
        storeId: shop.storeId || '',
        storeName: shop.storeName || 'Без названия',
        storeAddress: shop.storeAddress || ''
      }));

      const oldUserId = localStorage.getItem('poehali_user_id') || '';
      const isOldAnonymousUser = oldUserId && !oldUserId.startsWith('ecom_');
      
      if (isOldAnonymousUser) {
        try {
          const migrateResponse = await fetch('https://functions.poehali.dev/8effbced-c4d0-4505-816b-605f1eb102c9', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              old_user_id: oldUserId,
              ecomkassa_login: settings.ecomkassa_login
            })
          });
          
          if (migrateResponse.ok) {
            const migrateData = await migrateResponse.json();
            console.log('[MIGRATION] User migrated:', migrateData);
          }
        } catch (error) {
          console.error('[MIGRATION] Failed to migrate user:', error);
        }
      }
      
      setEcomkassaLogin(settings.ecomkassa_login);

      const updatedSettings = {
        ...settings,
        inn: taxIdentity,
        sno: taxVariant,
        available_shops: shops
      };

      setSettings(updatedSettings);
      await saveSettingsToServer(updatedSettings);
      toast.success(`Загружен профиль. Магазинов: ${shops.length}`);
      
      if (!updatedSettings.active_ai_provider) {
        setTimeout(() => {
          toast.info('⚠️ Не забудь подключить AI провайдера для обработки запросов', {
            duration: 5000
          });
        }, 1000);
      }
    } catch (error) {
      toast.error('Ошибка соединения с сервером');
    } finally {
      setIsLoadingShops(false);
    }
  };

  const handleShopSelect = async (shopId: string) => {
    const shop = settings.available_shops.find(s => s.storeId === shopId);
    if (shop) {
      const updatedSettings = {
        ...settings,
        group_code: shop.storeId,
        payment_address: shop.storeAddress
      };
      setSettings(updatedSettings);
      await saveSettingsToServer(updatedSettings);
      toast.info(`Выбран магазин: ${shop.storeName}`);
    }
  };

  const saveSettingsToServer = async (settingsToSave: IntegrationSettings) => {
    const userId = getUserId();
    
    try {
      const response = await fetch('https://functions.poehali.dev/e8972b95-5a58-4023-8f81-5385338d4590', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': userId
        },
        body: JSON.stringify({
          settings: {
            group_code: settingsToSave.group_code,
            inn: settingsToSave.inn,
            sno: settingsToSave.sno,
            default_vat: settingsToSave.default_vat,
            company_email: settingsToSave.company_email,
            payment_address: settingsToSave.payment_address,
            ecomkassa_login: settingsToSave.ecomkassa_login,
            ecomkassa_password: settingsToSave.ecomkassa_password,
            active_ai_provider: settingsToSave.active_ai_provider,
            gigachat_auth_key: settingsToSave.gigachat_auth_key,
            yandexgpt_api_key: settingsToSave.yandexgpt_api_key,
            yandexgpt_folder_id: settingsToSave.yandexgpt_folder_id,
            gptunnel_api_key: settingsToSave.gptunnel_api_key
          }
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save settings');
      }
    } catch (error) {
      console.error('[Settings] Failed to save to server:', error);
      throw error;
    }
  };

  const handleConnect = async (providerId: string, apiKey: string, folderId?: string) => {
    const keyMap: Record<string, string> = {
      gigachat: 'gigachat_auth_key',
      yandexgpt: 'yandexgpt_api_key',
      gptunnel_chatgpt: 'gptunnel_api_key',
      gptunnel_claude: 'gptunnel_api_key'
    };

    const key = keyMap[providerId];
    if (!key) return;

    const updatedSettings = {
      ...settings,
      [key]: apiKey,
      active_ai_provider: providerId
    };

    if (providerId === 'yandexgpt' && folderId) {
      updatedSettings.yandexgpt_folder_id = folderId;
    }

    setSettings(updatedSettings);
    
    await saveSettingsToServer(updatedSettings);
    
    const provider = aiProviders.find(p => p.id === providerId);
    toast.success(`Подключен провайдер: ${provider?.name}`);
  };

  const handleDisconnect = async () => {
    const currentProvider = settings.active_ai_provider;
    
    const keyMap: Record<string, string> = {
      gigachat: 'gigachat_auth_key',
      yandexgpt: 'yandexgpt_api_key',
      gptunnel_chatgpt: 'gptunnel_api_key',
      gptunnel_claude: 'gptunnel_api_key'
    };

    const key = keyMap[currentProvider];
    
    const updatedSettings = {
      ...settings,
      [key]: '',
      active_ai_provider: ''
    };

    setSettings(updatedSettings);
    await saveSettingsToServer(updatedSettings);

    if (currentProvider === 'yandexgpt') {
      updatedSettings.yandexgpt_folder_id = '';
    }

    toast.info('AI провайдер отключен');
  };

  const updateSettings = (updates: Partial<IntegrationSettings>) => {
    setSettings({ ...settings, ...updates });
  };

  const saveSettings = async () => {
    try {
      await saveSettingsToServer(settings);
      toast.success('Настройки сохранены');
    } catch (error) {
      toast.error('Ошибка сохранения настроек');
    }
  };

  return {
    settings,
    aiProviders,
    isLoadingShops,
    loadShops,
    handleShopSelect,
    handleConnect,
    handleDisconnect,
    updateSettings,
    saveSettings
  };
};