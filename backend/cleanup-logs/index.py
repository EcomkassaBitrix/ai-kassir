import json
import os
import psycopg2
from typing import Dict, Any
from datetime import datetime, timedelta


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Clean up old logs from database (older than 7 days)
    Args: event - dict with httpMethod
          context - object with attributes: request_id, function_name
    Returns: HTTP response dict with cleanup stats
    '''
    method: str = event.get('httpMethod', 'POST')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
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
    
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Database not configured'})
        }
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # Calculate cutoff date (7 days ago)
        cutoff_date = datetime.now() - timedelta(days=7)
        
        stats = {}
        
        # Clean telegram_previews (older than 7 days)
        cur.execute(
            "DELETE FROM telegram_previews WHERE created_at < %s",
            (cutoff_date,)
        )
        stats['telegram_previews_deleted'] = cur.rowcount
        
        # Clean telegram_edit_states (older than 7 days)
        cur.execute(
            "DELETE FROM telegram_edit_states WHERE created_at < %s",
            (cutoff_date,)
        )
        stats['telegram_edit_states_deleted'] = cur.rowcount
        
        # Clean telegram_links (expired and inactive, older than 7 days)
        cur.execute(
            "DELETE FROM telegram_links WHERE created_at < %s AND (is_active = FALSE OR expires_at < %s)",
            (cutoff_date, datetime.now())
        )
        stats['telegram_links_deleted'] = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[INFO] Cleanup completed: {stats}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Logs cleaned successfully',
                'stats': stats,
                'cutoff_date': cutoff_date.isoformat()
            })
        }
        
    except Exception as e:
        print(f"[ERROR] Cleanup failed: {e}")
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
