import json
import os
import psycopg2
from typing import Dict, Any

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Migrate old anonymous user to Ecomkassa-based user_id
    Args: event with old_user_id, ecomkassa_login; context with request_id
    Returns: HTTP response with new_user_id or conflict resolution
    '''
    method: str = event.get('httpMethod', 'POST')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-User-Id',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    if method != 'POST':
        return {
            'statusCode': 405,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    body = event.get('body', '{}')
    if body:
        body_data = json.loads(body)
    else:
        body_data = {}
    
    old_user_id = body_data.get('old_user_id')
    ecomkassa_login = body_data.get('ecomkassa_login')
    
    if not old_user_id or not ecomkassa_login:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'old_user_id and ecomkassa_login required'})
        }
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Database not configured'})
        }
    
    new_user_id = f'ecom_{ecomkassa_login}'
    
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    
    # Check if new_user_id already exists
    cur.execute('SELECT user_id FROM user_settings WHERE user_id = %s', (new_user_id,))
    existing = cur.fetchone()
    
    if existing:
        # Conflict: ecom_login already taken, generate fallback
        import random
        import time
        fallback_suffix = str(random.randint(1000, 9999)) + str(int(time.time()) % 10000)
        new_user_id = f'ecom_{ecomkassa_login}_{fallback_suffix}'
    
    # Migrate: Update old_user_id -> new_user_id in user_settings
    cur.execute(
        'UPDATE user_settings SET user_id = %s WHERE user_id = %s',
        (new_user_id, old_user_id)
    )
    
    # Migrate: Update old_user_id -> new_user_id in receipts table
    cur.execute(
        'UPDATE receipts SET user_id = %s WHERE user_id = %s',
        (new_user_id, old_user_id)
    )
    
    conn.commit()
    
    settings_migrated = cur.rowcount > 0
    
    cur.close()
    conn.close()
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'success': True,
            'new_user_id': new_user_id,
            'old_user_id': old_user_id,
            'migrated': settings_migrated,
            'conflict_resolved': existing is not None
        })
    }