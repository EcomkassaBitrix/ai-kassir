import json
import os
from typing import Dict, Any

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Get receipt history from database
    Args: event - dict with httpMethod, queryStringParameters
          context - object with attributes: request_id
    Returns: HTTP response dict with receipts list
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-User-Id',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    if method != 'GET':
        return {
            'statusCode': 405,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    query_params = event.get('queryStringParameters') or {}
    limit = int(query_params.get('limit', '50'))
    offset = int(query_params.get('offset', '0'))
    
    database_url = os.environ.get('DATABASE_URL', '')
    
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Database not configured'})
        }
    
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Проверяем, есть ли колонка payments
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 't_p7891941_voice_ai_agent_1' AND table_name = 'receipts' AND column_name = 'payments'"
        )
        has_payments = cursor.fetchone() is not None
        
        if has_payments:
            cursor.execute(
                f"SELECT id, external_id, user_message, operation_type, items, total, "
                f"payment_type, payments, customer_email, status, demo_mode, created_at, uuid "
                f"FROM receipts ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
            )
        else:
            cursor.execute(
                f"SELECT id, external_id, user_message, operation_type, items, total, "
                f"payment_type, customer_email, status, demo_mode, created_at, uuid "
                f"FROM receipts ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
            )
        
        receipts = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) as total FROM receipts")
        total_count = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        receipts_list = []
        for receipt in receipts:
            payment_type_display = receipt.get('payment_type', '1')
            
            # Если есть массив payments с несколькими типами оплаты
            if has_payments:
                try:
                    payments = receipt.get('payments')
                    if payments and isinstance(payments, list) and len(payments) > 1:
                        payment_types = [str(p.get('type', '1')) for p in payments if isinstance(p, dict)]
                        unique_types = list(dict.fromkeys(payment_types))  # Убираем дубликаты, сохраняя порядок
                        if len(unique_types) > 1:
                            payment_type_display = ', '.join(unique_types)
                except Exception:
                    # Если ошибка при парсинге payments, используем payment_type как есть
                    pass
            
            receipts_list.append({
                'id': receipt['id'],
                'external_id': receipt['external_id'],
                'user_message': receipt['user_message'],
                'operation_type': receipt['operation_type'],
                'items': receipt['items'],
                'total': float(receipt['total']),
                'payment_type': payment_type_display,
                'customer_email': receipt['customer_email'],
                'status': receipt['status'],
                'demo_mode': receipt['demo_mode'],
                'created_at': receipt['created_at'].isoformat() if receipt['created_at'] else None,
                'uuid': receipt.get('uuid')
            })
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'isBase64Encoded': False,
            'body': json.dumps({
                'success': True,
                'receipts': receipts_list,
                'total': total_count,
                'limit': limit,
                'offset': offset
            })
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }