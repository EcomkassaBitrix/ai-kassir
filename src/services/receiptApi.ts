const RECEIPT_API_URL = 'https://functions.poehali.dev/734da785-2867-4c5d-b20c-90fc6d86b11c';
const USER_SETTINGS_API_URL = 'https://functions.poehali.dev/e8972b95-5a58-4023-8f81-5385338d4590';

import { getUserId } from '@/utils/userId';

export const loadUserSettings = async () => {
  const userId = getUserId();
  
  try {
    const response = await fetch(USER_SETTINGS_API_URL, {
      headers: {
        'X-User-Id': userId
      }
    });

    if (!response.ok) {
      console.error('[Settings] Failed to load from server');
      return {};
    }

    const data = await response.json();
    return data.settings || {};
  } catch (error) {
    console.error('[Settings] Error loading settings:', error);
    return {};
  }
};

export const sendReceiptPreview = async (
  userInput: string,
  operationType: string,
  settings: any,
  lastReceiptData: any
) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 65000);

  try {
    const response = await fetch(RECEIPT_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: userInput,
        operation_type: operationType,
        preview_only: true,
        settings,
        previous_receipt: lastReceiptData
      }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
};

export const confirmReceipt = async (
  userInput: string,
  operationType: string,
  editedData: any,
  lastReceiptData: any,
  settings: any
) => {
  const externalId = `AI_${Date.now()}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 65000);
  
  try {
    const response = await fetch(RECEIPT_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: userInput,
        operation_type: operationType,
        preview_only: false,
        edited_data: editedData || lastReceiptData,
        external_id: externalId,
        settings
      }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
};