const USER_ID_KEY = 'poehali_user_id';
const ECOMKASSA_LOGIN_KEY = 'ecomkassa_login';

function generateUserId(): string {
  return 'user_' + Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
}

export function getUserId(): string {
  const ecomkassaLogin = localStorage.getItem(ECOMKASSA_LOGIN_KEY);
  
  if (ecomkassaLogin) {
    const userId = `ecom_${ecomkassaLogin}`;
    localStorage.setItem(USER_ID_KEY, userId);
    return userId;
  }
  
  let userId = localStorage.getItem(USER_ID_KEY);
  
  if (!userId) {
    userId = generateUserId();
    localStorage.setItem(USER_ID_KEY, userId);
    console.log('[USER_ID] Generated new user ID:', userId);
  }
  
  return userId;
}

export function setEcomkassaLogin(login: string): void {
  if (login) {
    localStorage.setItem(ECOMKASSA_LOGIN_KEY, login);
    const newUserId = `ecom_${login}`;
    localStorage.setItem(USER_ID_KEY, newUserId);
    console.log('[USER_ID] Switched to Ecomkassa-based user ID:', newUserId);
  }
}

export function clearEcomkassaLogin(): void {
  localStorage.removeItem(ECOMKASSA_LOGIN_KEY);
  const newUserId = generateUserId();
  localStorage.setItem(USER_ID_KEY, newUserId);
  console.log('[USER_ID] Cleared Ecomkassa login, generated new ID:', newUserId);
}