import json
import os
import psycopg2
import requests
import uuid
from typing import Dict, Any

def validate_gigachat_key(auth_key: str) -> Dict[str, Any]:
    '''Validate GigaChat auth key by getting access token'''
    try:
        response = requests.post(
            'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
            headers={
                'Authorization': f'Basic {auth_key}',
                'RqUID': str(uuid.uuid4()),
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={'scope': 'GIGACHAT_API_PERS'},
            timeout=10,
            verify=False
        )
        
        if response.status_code == 200:
            return {'valid': True, 'message': 'GigaChat key is valid'}
        else:
            return {'valid': False, 'message': f'Invalid key: {response.status_code}'}
    except Exception as e:
        return {'valid': False, 'message': f'Validation error: {str(e)}'}

def validate_yandexgpt_key(api_key: str, folder_id: str) -> Dict[str, Any]:
    '''Validate YandexGPT API key with test completion request'''
    try:
        response = requests.post(
            'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
            headers={
                'Authorization': f'Api-Key {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'modelUri': f'gpt://{folder_id}/yandexgpt-lite/latest',
                'completionOptions': {
                    'stream': False,
                    'temperature': 0.1,
                    'maxTokens': 10
                },
                'messages': [
                    {'role': 'user', 'text': 'test'}
                ]
            },
            timeout=15
        )
        
        if response.status_code == 200:
            return {'valid': True, 'message': 'YandexGPT key is valid'}
        else:
            return {'valid': False, 'message': f'Invalid key: {response.status_code}'}
    except Exception as e:
        return {'valid': False, 'message': f'Validation error: {str(e)}'}

def validate_yandex_speechkit_key(api_key: str) -> Dict[str, Any]:
    '''Validate Yandex SpeechKit API key by testing STT endpoint'''
    try:
        # Test with minimal audio data (1 second of silence in OGG)
        test_audio = b'\x4f\x67\x67\x53\x00\x02'
        
        response = requests.post(
            'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize',
            headers={
                'Authorization': f'Api-Key {api_key}'
            },
            params={
                'lang': 'ru-RU',
                'format': 'oggopus'
            },
            data=test_audio,
            timeout=10
        )
        
        # Even if transcription fails (empty audio), 200 status means key is valid
        if response.status_code == 200:
            return {'valid': True, 'message': 'Yandex SpeechKit key is valid'}
        elif response.status_code == 401:
            return {'valid': False, 'message': 'Invalid API key'}
        else:
            return {'valid': False, 'message': f'Validation error: {response.status_code}'}
    except Exception as e:
        return {'valid': False, 'message': f'Validation error: {str(e)}'}

def get_gptunnel_models(api_key: str) -> Dict[str, Any]:
    '''Fetch available models from GPTunnel API'''
    try:
        response = requests.get(
            'https://gptunnel.ru/v1/models',
            headers={'Authorization': api_key},
            timeout=15
        )
        
        if response.status_code != 200:
            return {'success': False, 'models': []}
        
        models_data = response.json()
        models = []
        for model in models_data.get('data', []):
            models.append({
                'id': model.get('id'),
                'name': model.get('title', model.get('id')),
                'type': model.get('type', 'TEXT')
            })
        
        return {'success': True, 'models': models}
    except Exception as e:
        return {'success': False, 'models': []}

def validate_gptunnel_key(api_key: str, model: str = None) -> Dict[str, Any]:
    '''Validate GPTunnel API key by fetching available models'''
    try:
        models_response = requests.get(
            'https://gptunnel.ru/v1/models',
            headers={'Authorization': api_key},
            timeout=15
        )
        
        if models_response.status_code != 200:
            return {'valid': False, 'message': f'Invalid key: {models_response.status_code}'}
        
        if not model:
            return {'valid': True, 'message': 'GPTunnel key is valid'}
        
        models_data = models_response.json()
        available_models = [m.get('id') for m in models_data.get('data', [])]
        
        if model not in available_models:
            return {'valid': False, 'message': f'Model {model} not found'}
        
        return {'valid': True, 'message': 'GPTunnel key and model are valid'}
    except Exception as e:
        return {'valid': False, 'message': f'Validation error: {str(e)}'}

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Manage AI provider settings with key validation (get providers, validate keys, set active provider)
    Args: event with httpMethod (GET/POST), headers with X-Admin-Token, body with provider_id
    Returns: Active provider info and available providers list with validation status
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Token',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    headers = event.get('headers', {})
    admin_token = headers.get('x-admin-token') or headers.get('X-Admin-Token')
    
    if not admin_token:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Unauthorized'})
        }
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Database not configured'})
        }
    
    available_providers = [
        {
            'id': 'gptunnel_chatgpt',
            'name': 'GPTunnel (мультимодели)',
            'description': 'Доступ к GPT, DeepSeek, Gemini и другим моделям',
            'secret_name': 'GPTUNNEL_API_KEY',
            'has_secret': bool(os.environ.get('GPTUNNEL_API_KEY'))
        },
        {
            'id': 'yandex_speechkit',
            'name': 'Yandex SpeechKit',
            'description': 'Распознавание голосовых сообщений (для Telegram бота)',
            'secret_name': None,
            'has_secret': False
        }
    ]
    
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    
    if method == 'GET':
        cur.execute("SELECT active_provider, selected_model, yandex_speechkit_key FROM ai_settings ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        active_provider = row[0] if row else ''
        selected_model = row[1] if row and len(row) > 1 else None
        yandex_speechkit_key = row[2] if row and len(row) > 2 else None
        
        # Update has_secret for yandex_speechkit based on DB
        for provider in available_providers:
            if provider['id'] == 'yandex_speechkit':
                provider['has_secret'] = bool(yandex_speechkit_key)
        
        response_data = {
            'active_provider': active_provider,
            'selected_model': selected_model,
            'available_providers': available_providers,
            'yandex_speechkit_key': yandex_speechkit_key if yandex_speechkit_key else None
        }
        
        if active_provider == 'gptunnel_chatgpt':
            api_key = os.environ.get('GPTUNNEL_API_KEY', '')
            if api_key:
                models_result = get_gptunnel_models(api_key)
                if models_result['success']:
                    response_data['available_models'] = models_result['models']
        
        cur.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'isBase64Encoded': False,
            'body': json.dumps(response_data)
        }
    
    if method == 'POST':
        body_data = json.loads(event.get('body', '{}'))
        provider_id: str = body_data.get('provider_id', '')
        selected_model: str = body_data.get('selected_model', None)
        yandex_speechkit_key: str = body_data.get('yandex_speechkit_key', None)
        
        if provider_id and provider_id not in [p['id'] for p in available_providers]:
            cur.close()
            conn.close()
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Invalid provider_id'})
            }
        
        provider = next((p for p in available_providers if p['id'] == provider_id), None)
        # Skip secret check for yandex_speechkit as it uses DB storage
        if provider_id and provider_id != 'yandex_speechkit' and provider and not provider['has_secret']:
            cur.close()
            conn.close()
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Secret {provider["secret_name"]} not configured'})
            }
        
        if not provider_id:
            validation_result = {'valid': True, 'message': 'Disabling provider'}
        elif provider_id == 'gigachat':
            auth_key = os.environ.get('GIGACHAT_AUTH_KEY', '')
            validation_result = validate_gigachat_key(auth_key)
        elif provider_id == 'yandexgpt':
            api_key = os.environ.get('YANDEXGPT_API_KEY', '')
            folder_id = os.environ.get('YANDEXGPT_FOLDER_ID', '')
            validation_result = validate_yandexgpt_key(api_key, folder_id)
        elif provider_id == 'gptunnel_chatgpt':
            api_key = os.environ.get('GPTUNNEL_API_KEY', '')
            validation_result = validate_gptunnel_key(api_key, selected_model)
        elif provider_id == 'yandex_speechkit':
            if not yandex_speechkit_key:
                cur.close()
                conn.close()
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'Yandex SpeechKit API key is required'})
                }
            validation_result = validate_yandex_speechkit_key(yandex_speechkit_key)
        else:
            validation_result = {'valid': False, 'message': 'Unknown provider'}
        
        if not validation_result['valid']:
            cur.close()
            conn.close()
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'error': 'Key validation failed',
                    'message': validation_result['message']
                })
            }
        
        cur.execute("SELECT COUNT(*) FROM ai_settings")
        count = cur.fetchone()[0]
        
        if count == 0:
            if provider_id == 'yandex_speechkit':
                cur.execute("INSERT INTO ai_settings (active_provider, selected_model, yandex_speechkit_key) VALUES (%s, %s, %s)", (provider_id, None, yandex_speechkit_key))
            else:
                cur.execute("INSERT INTO ai_settings (active_provider, selected_model) VALUES (%s, %s)", (provider_id, selected_model))
        else:
            if provider_id == 'yandex_speechkit':
                cur.execute("UPDATE ai_settings SET active_provider = %s, selected_model = %s, yandex_speechkit_key = %s, updated_at = CURRENT_TIMESTAMP WHERE id = (SELECT id FROM ai_settings ORDER BY id LIMIT 1)", (provider_id, None, yandex_speechkit_key))
            else:
                cur.execute("UPDATE ai_settings SET active_provider = %s, selected_model = %s, updated_at = CURRENT_TIMESTAMP WHERE id = (SELECT id FROM ai_settings ORDER BY id LIMIT 1)", (provider_id, selected_model))
        
        conn.commit()
        
        cur.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'isBase64Encoded': False,
            'body': json.dumps({
                'success': True,
                'active_provider': provider_id,
                'selected_model': selected_model,
                'validation': validation_result
            })
        }
    
    return {
        'statusCode': 405,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'error': 'Method not allowed'})
    }