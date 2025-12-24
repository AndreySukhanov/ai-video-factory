# Deployment Guide для DigitalOcean

## Информация о сервере

- **IP**: 64.23.158.28
- **OS**: Ubuntu 22.04 LTS
- **User**: root

## Шаг 1: Первоначальная настройка сервера

### 1.1 Подключитесь к серверу

```bash
ssh root@64.23.158.28
```

Пароль: `prM9R6WGdhKkG`

### 1.2 Запустите скрипт настройки сервера

```bash
# На сервере выполните:
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установите Docker Compose
apt-get install -y docker-compose-plugin

# Настройте файрвол
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp

# Создайте директорию для приложения
mkdir -p /opt/microdrama-ai
```

## Шаг 2: Загрузка кода на сервер

### Вариант A: Через Git (рекомендуется)

```bash
# На сервере
cd /opt/microdrama-ai
git clone https://github.com/AndreySukhanov/ai-video-factory.git .

# Или если репозиторий приватный, загрузите через ZIP
```

### Вариант B: Загрузка с локальной машины

```bash
# С вашей локальной машины (Windows)
# Используйте WinSCP или scp для загрузки файлов
scp -r C:\Users\Пользователь\Desktop\X4\AI_VIDEO\microdrama-ai root@64.23.158.28:/opt/microdrama-ai
```

## Шаг 3: Настройка окружения

```bash
# На сервере
cd /opt/microdrama-ai

# Создайте .env файл для backend
cp backend/.env.example backend/.env
nano backend/.env

# Добавьте ваши API ключи:
# OPENROUTER_API_KEY=sk-or-v1-xxxxx
# REPLICATE_API_TOKEN=r8_xxxxx
# FAL_KEY=xxxxx (если используете)
```

## Шаг 4: Запуск приложения

```bash
# На сервере
cd /opt/microdrama-ai

# Скопируйте production config
cp docker-compose.prod.yml docker-compose.yml

# Запустите приложение
docker compose up -d --build

# Проверьте статус
docker compose ps

# Посмотрите логи
docker compose logs -f
```

## Шаг 5: Проверка работоспособности

Откройте в браузере:
- Frontend: http://64.23.158.28
- Backend API: http://64.23.158.28/api/v1/docs

## Управление приложением

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Отдельный сервис
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f worker
```

### Перезапуск

```bash
# Перезапустить все
docker compose restart

# Перезапустить конкретный сервис
docker compose restart backend
```

### Обновление кода

```bash
cd /opt/microdroma-ai
git pull origin main
docker compose down
docker compose up -d --build
```

### Остановка

```bash
docker compose down
```

### Очистка (удаление данных)

```bash
docker compose down -v
```

## Настройка SSL (HTTPS)

### Опция 1: Let's Encrypt (рекомендуется)

```bash
# Установите certbot
apt-get install -y certbot python3-certbot-nginx

# Получите сертификат (замените your-domain.com)
certbot --nginx -d your-domain.com

# Certbot автоматически обновит nginx конфигурацию
```

### Опция 2: Cloudflare (если используете)

1. Добавьте домен в Cloudflare
2. Включите Proxy (оранжевое облако)
3. SSL/TLS режим: "Full" или "Full (strict)"
4. В Cloudflare DNS добавьте A-запись: `@` → `64.23.158.28`

## Мониторинг ресурсов

```bash
# Использование контейнерами
docker stats

# Системные ресурсы
htop

# Дисковое пространство
df -h

# Использование Docker
docker system df
```

## Troubleshooting

### Контейнеры не запускаются

```bash
# Проверьте логи
docker compose logs

# Проверьте конфигурацию
docker compose config

# Пересоздайте контейнеры
docker compose down
docker compose up -d --build --force-recreate
```

### Недостаточно памяти

```bash
# Добавьте swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Порты заняты

```bash
# Проверьте какие порты используются
netstat -tulpn | grep LISTEN

# Или
ss -tulpn | grep LISTEN

# Остановите конфликтующие процессы
sudo systemctl stop apache2  # если запущен Apache
sudo systemctl stop nginx    # если запущен Nginx системный
```

## Backup

### Создание резервной копии

```bash
# Остановите приложение
docker compose down

# Создайте backup
cd /opt
tar -czf microdrama-ai-backup-$(date +%Y%m%d).tar.gz microdrama-ai/

# Скачайте на локальную машину
# scp root@64.23.158.28:/opt/microdrama-ai-backup-*.tar.gz ./
```

### Восстановление

```bash
# Загрузите backup на сервер
scp ./microdrama-ai-backup-*.tar.gz root@64.23.158.28:/opt/

# На сервере
cd /opt
tar -xzf microdrama-ai-backup-*.tar.gz
cd microdrama-ai
docker compose up -d
```

## Безопасность

### Рекомендации:

1. **Смените пароль root**:
```bash
passwd
```

2. **Создайте отдельного пользователя**:
```bash
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy
```

3. **Настройте SSH ключи** вместо пароля

4. **Отключите root login через SSH**:
```bash
nano /etc/ssh/sshd_config
# Установите: PermitRootLogin no
systemctl restart sshd
```

5. **Используйте fail2ban**:
```bash
apt-get install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

## Поддержка

Если возникли проблемы:
1. Проверьте логи: `docker compose logs -f`
2. Проверьте статус: `docker compose ps`
3. Проверьте .env файлы
4. Проверьте доступные ресурсы: `free -h`, `df -h`
