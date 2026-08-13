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
    
    headers_in = event.get('headers') or {}
    user_id = headers_in.get('X-User-Id') or headers_in.get('x-user-id', '')
    
    if not user_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'X-User-Id header is required'})
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
        
        cursor.execute(
            "SELECT id, external_id, user_id, user_message, operation_type, items, total, "
            "payment_type, payments, customer_email, status, demo_mode, created_at, uuid "
            "FROM receipts WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset)
        )
        
        receipts = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) as total FROM receipts WHERE user_id = %s", (user_id,))
        total_count = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        receipts_list = []
        for receipt in receipts:
            payment_type_display = receipt.get('payment_type', '1')
            
            # Если есть массив payments с несколькими типами оплаты
            try:
                payments = receipt.get('payments')
                if payments and isinstance(payments, list) and len(payments) > 1:
                    payment_types = [str(p.get('type', '1')) for p in payments if isinstance(p, dict)]
                    unique_types = list(dict.fromkeys(payment_types))
                    if len(unique_types) > 1:
                        payment_type_display = ', '.join(unique_types)
            except Exception:
                pass
            
            receipts_list.append({
                'id': receipt['id'],
                'external_id': receipt['external_id'],
                'user_id': receipt.get('user_id'),
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