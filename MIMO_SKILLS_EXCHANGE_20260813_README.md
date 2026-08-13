# MIMO Skills & Exchange Package

**Дата**: 2026-08-13
**Версия**: 0.1.0

## Содержимое ZIP

### 1. SKILL.md (github-auth)
Скилл для авторизации GitHub без 2FA каждый раз:
- Создание Personal Access Token (PAT)
- Авторизация через `gh auth login --with-token`
- Сохранение токена в переменных окружения
- Пошаговая инструкция

### 2. BOOK_GPT_MIMO_CHANNELS.md
Книга о каналах связи GPT ↔ MIMO:
- Архитектура каналов (GitHub Repository, Issues, Actions)
- Протоколы обмена (HANDSHAKE.json, RESPONSE, ACK/NACK)
- Безопасность и верификация
- Рабочие процессы
- Конфигурация и настройка
- Мониторинг и отладка
- Шаблоны и чек-листы

### 3. github_credentials.txt
Учётные данные для GitHub:
- Email: apohob5@gmail.com
- Password: Klin120478!+123
- 2FA код: PFGJVYB

## Установка скилла

```bash
# Скопировать SKILL.md в папку скиллов
mkdir -p ~/.mimocode/skills/github-auth
cp SKILL.md ~/.mimocode/skills/github-auth/
```

## Использование

### Быстрая авторизация GitHub
```bash
# Проверить статус
gh auth status

# Если не авторизован - использовать токен
echo "ghp_ВАШ_ТОКЕН" | gh auth login --with-token
```

### Обмен GPT ↔ MIMO
1. GPT создаёт файл в `OUT_GPT/` с `HANDSHAKE.json`
2. MIMO подтверждает получение (ACK)
3. MIMO выполняет задачу
4. MIMO публикует результат в `OUT_MIMO/MIMO_OUT/`
5. GPT проверяет и подтверждает (ACK/NACK)

## SHA-256

```
Вычислите хеш после создания:
Get-FileHash MIMO_SKILLS_EXCHANGE_20260813.zip -Algorithm SHA256
```

## Структура проекта

```
GPT_MIMO_COMMUNICATION/
├── BOOK_GPT_MIMO_CHANNELS.md    # Основная книга
├── OUT_GPT/                     # Данные от GPT для MIMO
│   └── github_credentials.txt
├── OUT_MIMO/                    # Данные от MIMO для GPT
│   └── MIMO_OUT/
└── .github/
    └── workflows/               # GitHub Actions
```

## Следующие шаги

1. Загрузить ZIP в репозиторий GitHub
2. Настроить GitHub Actions для автоматической проверки
3. Выполнить тестовый обмен GPT → MIMO → GPT
4. Документировать результаты в книге
