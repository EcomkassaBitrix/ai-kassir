#!/bin/bash

# Скрипт для настройки автоматической очистки логов на VPS
# Запускает cleanup-logs функцию каждые 7 дней

CLEANUP_URL="https://functions.poehali.dev/e27e2e41-9cdf-48bf-9e15-ce6cb962c908"

# Создаём скрипт для вызова функции очистки
cat > /usr/local/bin/cleanup-logs.sh << 'EOF'
#!/bin/bash
# Вызываем Cloud Function для очистки логов
curl -X POST "https://functions.poehali.dev/e27e2e41-9cdf-48bf-9e15-ce6cb962c908" \
  -H "Content-Type: application/json" \
  -s -o /tmp/cleanup-logs.log

# Логируем результат
echo "[$(date)] Cleanup executed" >> /var/log/cleanup-logs.log
cat /tmp/cleanup-logs.log >> /var/log/cleanup-logs.log
EOF

# Делаем скрипт исполняемым
chmod +x /usr/local/bin/cleanup-logs.sh

# Добавляем задачу в crontab (каждые 7 дней в 03:00)
# Проверяем, есть ли уже такая задача
if ! crontab -l 2>/dev/null | grep -q "cleanup-logs.sh"; then
    # Добавляем новую задачу
    (crontab -l 2>/dev/null; echo "0 3 */7 * * /usr/local/bin/cleanup-logs.sh") | crontab -
    echo "✅ Cron job добавлен: очистка логов каждые 7 дней в 03:00"
else
    echo "ℹ️ Cron job уже существует"
fi

# Показываем текущие задачи cron
echo ""
echo "Текущие задачи cron:"
crontab -l

echo ""
echo "📝 Логи будут сохраняться в: /var/log/cleanup-logs.log"
echo "🧪 Тестовый запуск: /usr/local/bin/cleanup-logs.sh"
