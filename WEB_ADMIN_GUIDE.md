# Web-админка

Web-админка работает отдельно от Telegram-бота и использует ту же SQLite БД.
Telegram-бот по-прежнему запускается через `main.py`.

## Подготовка

```bash
cd /root/vpn-panel-01
source venv/bin/activate
pip install -r requirements.txt
python -c "from database.migrations import run_migrations; run_migrations(); print('ok')"
python tools/create_web_admin.py
```

## Ручной запуск

```bash
cd /root/vpn-panel-01
source venv/bin/activate
WEB_HOST=0.0.0.0 WEB_PORT=8080 python web_main.py
```

Откройте `http://SERVER_IP:8080/login` или `http://127.0.0.1:8080/login` с самого сервера.

Корневой адрес `/` перенаправляет на `/login`.

Installer creates new Web env files with `WEB_HOST=0.0.0.0`, so direct LAN access such as `http://10.5.2.57:8080/` works without extra edits. For production, restrict access with firewall rules or put the service behind a reverse proxy with HTTPS.

## systemd

`install.sh install`, `install.sh update` and `install.sh reset` install and restart both services:

- `yadreno-vpn` for the Telegram bot;
- `yadreno-vpn-web` for the Web admin.

The installer creates `/etc/yadreno-vpn/web.env` once and preserves it on future updates/resets. Keep `WEB_SECRET_KEY` there stable, otherwise active Web sessions will be invalidated after restart.

On first install the script asks for the Web admin username and password when they are not passed as arguments. For non-interactive installs pass them explicitly:

```bash
bash install.sh install <BOT_TOKEN> <ADMIN_ID> <WEB_ADMIN_USERNAME> <WEB_ADMIN_PASSWORD>
```

If an admin already exists in `admin_users`, install/update/reset keep it unchanged.

```bash
cp yadreno-vpn-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now yadreno-vpn-web
systemctl status yadreno-vpn-web
```

## Reverse proxy

Публикуйте Web-админку только через HTTPS и reverse proxy. Не открывайте порт
`8080` напрямую в интернет. Для production задайте стабильный секрет:

```bash
install -d -m 700 /etc/yadreno-vpn
cat > /etc/yadreno-vpn/web.env <<'EOF'
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_SECRET_KEY=replace-with-long-random-secret
EOF
chmod 600 /etc/yadreno-vpn/web.env
systemctl restart yadreno-vpn-web
```

Лучше положить его в systemd `EnvironmentFile`, чтобы сессии не сбрасывались
после перезапуска.

## Что уже есть в MVP

- login/logout через cookie-сессию;
- dashboard;
- просмотр и базовое управление серверами, тарифами, пользователями, ключами;
- просмотр платежей;
- базовые настройки;
- просмотр/скачивание/очистка `logs/bot.log`;
- audit log действий Web-администраторов.

Опасные действия требуют подтверждения в браузере и пишутся в audit log.
