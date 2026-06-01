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
- редактирование страниц Telegram-бота в `/admin/pages`: текст, изображение, JSON кнопок, предпросмотр, валидация и сброс custom-значений;
- просмотр/скачивание/очистка `logs/bot.log`;
- audit log действий Web-администраторов.

Опасные действия требуют подтверждения в браузере и пишутся в audit log.

## Редактор страниц бота

Раздел `/admin/pages` работает с существующей таблицей `pages`. Он не создает отдельное хранилище: Web меняет только `text_custom`, `image_custom` и `buttons_custom`, а `*_default` продолжают обновляться миграциями.

В редакторе можно:

- посмотреть все страницы и статус custom/default;
- изменить Telegram HTML текст;
- задать изображение как `http://`, `https://` URL или Telegram `file_id`;
- изменить кнопки через JSON;
- проверить HTML, image и JSON перед сохранением;
- сбросить custom текст, изображение или кнопки к default;
- посмотреть безопасный Web preview Telegram HTML и кнопок.

Каждое сохранение и сброс пишутся в `admin_audit_log` с action `page.update` или `page.reset`.

### Поиск, группы и предпросмотр

В `/admin/pages` есть поиск по `page_key`, человекочитаемому названию, `text_default` и `text_custom`. Фильтр группирует страницы на главные, покупку, ключи, оплаты, ошибки и прочее.

У каждой страницы есть:

- `default` - значения из миграций проекта;
- `custom` - значения администратора из Web или Telegram-редактора;
- отдельная preview-страница `/admin/pages/{page_key}/preview`.

Preview показывает источник текста, картинки и кнопок, безопасный браузерный предпросмотр Telegram HTML, визуальную сетку кнопок по `row`/`col`, raw effective text и raw effective buttons JSON.

### Редактирование

Текст сохраняется в `text_custom` и должен использовать поддерживаемый Telegram HTML. Картинка сохраняется в `image_custom`; допустимы `http://`, `https://` и Telegram `file_id`. Локальные пути, `data:` и `javascript:` запрещены.

Кнопки редактируются через `buttons_custom` JSON. Можно скопировать `buttons_default` в custom, отредактировать копию и сохранить. Сброс текста, картинки и кнопок выполняется отдельными действиями:

- `POST /admin/pages/{page_key}/reset-text`;
- `POST /admin/pages/{page_key}/reset-image`;
- `POST /admin/pages/{page_key}/reset-buttons`.

Каждое изменение пишет audit log: `page.update`, `page.reset_text`, `page.reset_image`, `page.reset_buttons`, `page.copy_default_buttons`.

### Переменные страниц

В редакторе показываются известные переменные конкретной страницы, например `%тарифы%`, `%списокключей%`, `%ключ%`, `%ссылка%`, `%данныеэкрана%`. Кнопка "Скопировать" вставляет имя переменной в буфер обмена. Если для страницы специальных переменных нет, Web показывает отдельное сообщение.

### Пример JSON кнопок

```json
[
  {
    "id": "btn_buy_key",
    "label": "💳 Купить ключ",
    "color": "secondary",
    "row": 0,
    "col": 0,
    "is_hidden": false,
    "action_type": "internal",
    "action_value": "cmd_buy"
  }
]
```
