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
WEB_HOST=127.0.0.1 WEB_PORT=8080 python web_main.py
```

Откройте `http://127.0.0.1:8080/login` с сервера или через SSH tunnel.

## systemd

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
export WEB_SECRET_KEY="long-random-secret"
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

