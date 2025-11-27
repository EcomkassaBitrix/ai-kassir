import json
import os
import urllib.request
from typing import Dict, Any


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Check available models in GPTunnel API
    Args: event - dict with httpMethod
          context - object with request_id
    Returns: HTTP response with models list
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    api_key = os.environ.get('GPTUNNEL_API_KEY')
    if not api_key:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'API key not configured'})
        }
    
    try:
        results = {}
        
        # Check standard models endpoint
        try:
            models_url = 'https://gptunnel.ru/v1/models'
            models_req = urllib.request.Request(
                models_url,
                headers={'Authorization': f'Bearer {api_key}'},
                method='GET'
            )
            models_resp = urllib.request.urlopen(models_req, timeout=10)
            results['standard_models'] = json.loads(models_resp.read().decode('utf-8'))
        except Exception as e:
            results['standard_models_error'] = str(e)
        
        # Check media models endpoint  
        try:
            media_url = 'https://gptunnel.ru/v1/media/models'
            media_req = urllib.request.Request(
                media_url,
                headers={'Authorization': f'Bearer {api_key}'},
                method='GET'
            )
            media_resp = urllib.request.urlopen(media_req, timeout=10)
            results['media_models'] = json.loads(media_resp.read().decode('utf-8'))
        except Exception as e:
            results['media_models_error'] = str(e)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'results': results
            }, ensure_ascii=False)
        }
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        return {
            'statusCode': e.code,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'error': f'HTTP {e.code}',
                'details': error_body
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }