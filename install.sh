#!/bin/bash

# Yadreno VPN — скрипт установки и управления
# Запуск: bash <(curl -sL https://raw.githubusercontent.com/zirocool93/vpn-panel-01/main/install.sh)
# 
# === АВТОМАТИЧЕСКИЙ ЗАПУСК (БЕЗ ДИАЛОГОВ) ===
#
# 1. Запуск прямо с GitHub (для чистой установки или если папки ещё нет):
# bash <(curl -sL https://raw.githubusercontent.com/zirocool93/vpn-panel-01/main/install.sh) install <BOT_TOKEN> <ADMIN_ID> [WEB_ADMIN_USERNAME] [WEB_ADMIN_PASSWORD]
# bash <(curl -sL https://raw.githubusercontent.com/zirocool93/vpn-panel-01/main/install.sh) update [COMMIT_OR_BRANCH]
# bash <(curl -sL https://raw.githubusercontent.com/zirocool93/vpn-panel-01/main/install.sh) reset [COMMIT_OR_BRANCH]
#
# 2. Локальный запуск (если репозиторий уже установлен и нужно просто обновить/сбросить):
# bash install.sh update [COMMIT_OR_BRANCH]
# bash install.sh reset [COMMIT_OR_BRANCH]

set -e

INSTALL_DIR="/root/vpn-panel-01"
REPO_URL="https://github.com/zirocool93/vpn-panel-01.git"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_FILE="yadreno-vpn.service"
WEB_SERVICE_FILE="yadreno-vpn-web.service"
WEB_ENV_DIR="/etc/yadreno-vpn"
WEB_ENV_FILE="$WEB_ENV_DIR/web.env"
BOT_DB_RELATIVE_PATH="database/vpn_bot.db"
BACKUP_DIR="$INSTALL_DIR/backups"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}========================================${NC}\n"
}

print_ok() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_err() {
    echo -e "${RED}[✗]${NC} $1"
}

# Запрос настроек у пользователя
ask_config() {
    print_header "Настройка конфигурации"

    if [ "$AUTO_MODE" = "1" ]; then
        NEED_WRITE_CONFIG=1
        print_ok "Автоматический режим: используем переданные параметры"
        return 0
    fi

    if [ -f "$INSTALL_DIR/config.py" ]; then
        echo -e "${YELLOW}Обнаружен существующий config.py${NC}"
        read -p "Использовать существующие настройки? (Y/n): " use_existing
        use_existing=${use_existing:-Y}
        if [[ "$use_existing" =~ ^[YyДд]$ ]]; then
            print_ok "Используем существующий config.py"
            return 0
        fi
    fi

    echo ""
    echo -e "${CYAN}Введите данные для настройки бота:${NC}"
    echo ""

    while true; do
        read -p "BOT_TOKEN (от @BotFather): " bot_token
        if [ -n "$bot_token" ]; then
            break
        fi
        print_err "BOT_TOKEN не может быть пустым!"
    done

    while true; do
        read -p "ADMIN_IDS (ваш Telegram ID): " admin_id
        if [ -n "$admin_id" ] && [[ "$admin_id" =~ ^[0-9]+$ ]]; then
            break
        fi
        print_err "ADMIN_IDS должен быть числом!"
    done

    BOT_TOKEN="$bot_token"
    ADMIN_ID="$admin_id"
    NEED_WRITE_CONFIG=1
    print_ok "Данные получены"
}

# Создание/обновление config.py
write_config() {
    if [ "$NEED_WRITE_CONFIG" != "1" ]; then
        return 0
    fi

    cp "$INSTALL_DIR/config.py.example" "$INSTALL_DIR/config.py"

    sed -i "s|\"ВАШ_ТОКЕН_БОТА\"|\"$BOT_TOKEN\"|g" "$INSTALL_DIR/config.py"
    sed -i "s|12345678|$ADMIN_ID|g" "$INSTALL_DIR/config.py"

    print_ok "config.py создан с вашими настройками"
}

# Установка системных пакетов
install_system_deps() {
    print_header "Установка системных зависимостей"

    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a

    apt-get update -qq
    apt-get install -y -qq \
        python3-venv \
        python3-pip \
        git \
        > /dev/null 2>&1

    print_ok "Системные пакеты обновлены"
    print_ok "python3-venv, python3-pip, git установлены"
}

# Создание виртуального окружения и установка зависимостей
setup_venv() {
    print_header "Настройка виртуального окружения Python"

    python3 -m venv "$VENV_DIR"
    print_ok "Виртуальное окружение создано: $VENV_DIR"

    "$VENV_DIR/bin/python" -m pip install --upgrade pip -q
    "$VENV_DIR/bin/python" -m pip install --upgrade -r "$INSTALL_DIR/requirements.txt" -q

    print_ok "Зависимости Python установлены в venv"
}

update_python_deps() {
    print_header "Обновление Python-зависимостей"

    if [ ! -x "$VENV_DIR/bin/python" ]; then
        print_warn "Виртуальное окружение не найдено — создаём заново"
        python3 -m venv "$VENV_DIR"
    fi

    "$VENV_DIR/bin/python" -m pip install --upgrade pip -q
    "$VENV_DIR/bin/python" -m pip install --upgrade -r "$INSTALL_DIR/requirements.txt" -q

    print_ok "Зависимости Python обновлены"
}

# Настройка systemd сервиса
setup_web_env() {
    mkdir -p "$WEB_ENV_DIR"

    if [ ! -f "$WEB_ENV_FILE" ]; then
        python_bin="$VENV_DIR/bin/python"
        if [ ! -x "$python_bin" ]; then
            python_bin="python3"
        fi
        web_secret="$("$python_bin" - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
        cat > "$WEB_ENV_FILE" << EOF
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_SECRET_KEY=$web_secret
WEB_COOKIE_SECURE=0
WEB_COOKIE_SAMESITE=lax
EOF
        chmod 600 "$WEB_ENV_FILE"
        print_ok "Web env created: $WEB_ENV_FILE"
    else
        chmod 600 "$WEB_ENV_FILE"
        print_ok "Web env preserved: $WEB_ENV_FILE"
    fi
}

setup_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"
    print_ok "Backup directory ready: $BACKUP_DIR"
}

run_database_migrations() {
    print_header "Applying database migrations"
    "$VENV_DIR/bin/python" -c "from database.migrations import run_migrations; run_migrations(); print('ok')"
    print_ok "Database migrations applied"
}

web_admin_exists() {
    "$VENV_DIR/bin/python" - <<'PY'
from database.connection import get_db
from database.migrations import run_migrations

run_migrations()
with get_db() as conn:
    row = conn.execute("SELECT COUNT(*) AS count FROM admin_users").fetchone()
raise SystemExit(0 if row and row["count"] else 1)
PY
}

setup_initial_web_admin() {
    print_header "Web admin user"

    if web_admin_exists; then
        print_ok "Web admin already exists"
        return 0
    fi

    if [ -z "$WEB_ADMIN_USERNAME" ] || [ -z "$WEB_ADMIN_PASSWORD" ]; then
        if [ ! -t 0 ]; then
            if [ "$REQUIRE_WEB_ADMIN" = "1" ]; then
                print_err "Web admin username/password are required for first install."
                echo "Usage: bash install.sh install <BOT_TOKEN> <ADMIN_ID> <WEB_ADMIN_USERNAME> <WEB_ADMIN_PASSWORD>"
                return 1
            fi
            print_warn "Web admin was not created: WEB_ADMIN_USERNAME/WEB_ADMIN_PASSWORD are not set."
            echo "Run later: cd $INSTALL_DIR && source venv/bin/activate && python tools/create_web_admin.py"
            return 0
        fi

        while true; do
            read -p "Web admin username [admin]: " web_admin_username
            web_admin_username=${web_admin_username:-admin}
            if [ -n "$web_admin_username" ]; then
                break
            fi
            print_err "Web admin username cannot be empty"
        done

        while true; do
            read -s -p "Web admin password: " web_admin_password
            echo ""
            read -s -p "Confirm Web admin password: " web_admin_password_confirm
            echo ""
            if [ "$web_admin_password" != "$web_admin_password_confirm" ]; then
                print_err "Passwords do not match"
                continue
            fi
            if [ "${#web_admin_password}" -lt 8 ]; then
                print_err "Password must be at least 8 characters"
                continue
            fi
            break
        done

        WEB_ADMIN_USERNAME="$web_admin_username"
        WEB_ADMIN_PASSWORD="$web_admin_password"
    fi

    WEB_ADMIN_SKIP_IF_EXISTS=1 \
    WEB_ADMIN_USERNAME="$WEB_ADMIN_USERNAME" \
    WEB_ADMIN_PASSWORD="$WEB_ADMIN_PASSWORD" \
        "$VENV_DIR/bin/python" "$INSTALL_DIR/tools/create_web_admin.py"
    print_ok "Web admin user is ready"
}

setup_systemd() {
    print_header "Настройка автозапуска (systemd)"

    cat > "$INSTALL_DIR/$SERVICE_FILE" << EOF
[Unit]
Description=Yadreno VPN Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    cat > "$INSTALL_DIR/$WEB_SERVICE_FILE" << EOF
[Unit]
Description=Yadreno VPN Web Admin
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$WEB_ENV_FILE
ExecStart=$VENV_DIR/bin/python web_main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    setup_web_env
    setup_backup_dir
    cp "$INSTALL_DIR/$SERVICE_FILE" /etc/systemd/system/
    cp "$INSTALL_DIR/$WEB_SERVICE_FILE" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable yadreno-vpn > /dev/null 2>&1
    systemctl enable yadreno-vpn-web > /dev/null 2>&1

    print_ok "systemd сервис установлен и включён в автозапуск"
}

check_runtime_environment() {
    print_header "Проверка окружения"

    if ! command -v systemctl >/dev/null 2>&1; then
        print_err "systemctl не найден. Для автозапуска нужен контейнер/сервер с systemd."
        exit 1
    fi

    if [ ! -d /run/systemd/system ]; then
        print_err "systemd не запущен как init-система."
        echo "Для LXC Proxmox используйте Ubuntu 24.04 container template с systemd и запускайте скрипт внутри запущенного контейнера."
        exit 1
    fi

    if ! systemctl is-system-running --quiet 2>/dev/null; then
        system_state="$(systemctl is-system-running 2>/dev/null || true)"
        case "$system_state" in
            running|degraded|starting|initializing)
                print_warn "systemd состояние: $system_state. Продолжаем."
                ;;
            *)
                print_err "systemd состояние: ${system_state:-unknown}. systemctl может не работать в этом окружении."
                exit 1
                ;;
        esac
    fi

    print_ok "systemd доступен"
}

# Запуск сервиса
check_lxc_vpn_device() {
    if [ ! -c /dev/net/tun ]; then
        print_warn "/dev/net/tun not found. VPN features in Proxmox LXC require TUN passthrough."
        echo "Proxmox CT config example:"
        echo "  lxc.cgroup2.devices.allow: c 10:200 rwm"
        echo "  lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file"
    fi
}

start_service() {
    systemctl start yadreno-vpn
    systemctl start yadreno-vpn-web
    sleep 2

    if systemctl is-active --quiet yadreno-vpn; then
        print_ok "Бот запущен и работает!"
    else
        print_err "Бот не запустился. Проверьте логи:"
        echo "  systemctl status yadreno-vpn"
        echo "  journalctl -u yadreno-vpn -n 50"
    fi

    if systemctl is-active --quiet yadreno-vpn-web; then
        print_ok "Web admin is running"
    else
        print_err "Web admin failed to start. Check logs:"
        echo "  systemctl status yadreno-vpn-web"
        echo "  journalctl -u yadreno-vpn-web -n 50"
    fi
}

# ============================================================
# ПУНКТ 1: УСТАНОВКА
# ============================================================
do_install() {
    print_header "🚀 Установка Yadreno VPN"
    check_runtime_environment
    check_lxc_vpn_device

    # Проверяем, не установлен ли уже
    if [ -d "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR/.git" ]; then
        print_warn "Yadreno VPN уже установлен в $INSTALL_DIR"
        if [ "$AUTO_MODE" = "1" ]; then
            print_warn "Автоматический режим: принудительная переустановка"
            reinstall_choice="1"
        else
            echo ""
            echo "  1) Переустановить (удалить и установить заново)"
            echo "  2) Отмена"
            read -p "Выберите [1-2]: " reinstall_choice
        fi
        if [ "$reinstall_choice" != "1" ]; then
            echo "Установка отменена."
            return 0
        fi
        systemctl stop yadreno-vpn 2>/dev/null || true
        systemctl stop yadreno-vpn-web 2>/dev/null || true
        # Сохраняем config.py и базу данных
        if [ -f "$INSTALL_DIR/config.py" ]; then
            cp "$INSTALL_DIR/config.py" /tmp/yadreno_config_backup.py
            BACKUP_CONFIG=1
        fi
        if [ -f "$INSTALL_DIR/$BOT_DB_RELATIVE_PATH" ]; then
            cp "$INSTALL_DIR/$BOT_DB_RELATIVE_PATH" /tmp/yadreno_db_backup.db
            BACKUP_DB=1
        fi
        rm -rf "$INSTALL_DIR"
    fi

    # Запрашиваем настройки до начала установки
    ask_config

    # Установка системных зависимостей
    install_system_deps

    # Клонирование репозитория
    print_header "Загрузка Yadreno VPN"
    git clone "$REPO_URL" "$INSTALL_DIR" -q
    cd "$INSTALL_DIR"
    print_ok "Репозиторий клонирован"

    # Восстановление backup'ов при переустановке
    if [ "$BACKUP_CONFIG" = "1" ] && [ -f "/tmp/yadreno_config_backup.py" ]; then
        cp /tmp/yadreno_config_backup.py "$INSTALL_DIR/config.py"
        rm /tmp/yadreno_config_backup.py
        print_ok "config.py восстановлен из резервной копии"
        NEED_WRITE_CONFIG=0
    fi
    if [ "$BACKUP_DB" = "1" ] && [ -f "/tmp/yadreno_db_backup.db" ]; then
        mkdir -p "$INSTALL_DIR/$(dirname "$BOT_DB_RELATIVE_PATH")"
        cp /tmp/yadreno_db_backup.db "$INSTALL_DIR/$BOT_DB_RELATIVE_PATH"
        rm /tmp/yadreno_db_backup.db
        print_ok "База данных восстановлена из резервной копии"
    fi

    # Запись config.py
    write_config

    # Виртуальное окружение и зависимости
    setup_venv
    run_database_migrations
    REQUIRE_WEB_ADMIN=1
    setup_initial_web_admin

    # Настройка автозапуска
    setup_systemd

    # Запуск
    print_header "Запуск бота"
    start_service

    print_header "✅ Установка завершена!"
    echo -e "  Директория: ${GREEN}$INSTALL_DIR${NC}"
    echo -e "  Виртуальное окружение: ${GREEN}$VENV_DIR${NC}"
    echo -e "  Управление сервисом:"
    echo -e "    ${CYAN}systemctl status yadreno-vpn${NC}   — статус"
    echo -e "    ${CYAN}systemctl restart yadreno-vpn${NC}  — перезапуск"
    echo -e "    ${CYAN}systemctl stop yadreno-vpn${NC}     — остановка"
    echo -e "    ${CYAN}journalctl -u yadreno-vpn -f${NC}   — логи"
}

# ============================================================
# ПУНКТ 2: МЯГКОЕ ОБНОВЛЕНИЕ (git pull)
# ============================================================
do_soft_update() {
    print_header "🔄 Мягкое обновление"
    check_runtime_environment
    check_lxc_vpn_device

    if [ ! -d "$INSTALL_DIR/.git" ]; then
        print_err "Yadreno VPN не установлен в $INSTALL_DIR"
        return 1
    fi

    cd "$INSTALL_DIR"

    # Сохраняем текущие изменения в stash (если есть)
    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
        print_warn "Обнаружены локальные изменения — сохраняем через git stash"
        git stash -q
        STASHED=1
    fi

    if [ -n "$TARGET_COMMIT" ]; then
        git fetch -q origin
        git checkout -q "$TARGET_COMMIT"
    else
        git checkout -q main
        git pull -q origin main
    fi

    if [ "$STASHED" = "1" ]; then
        git stash pop -q 2>/dev/null || print_warn "Не удалось восстановить локальные изменения (конфликт)"
    fi

    print_ok "Код обновлён"

    # Применяем возможные изменения systemd unit и обновляем зависимости
    setup_systemd
    update_python_deps
    run_database_migrations
    setup_initial_web_admin

    # Перезапуск
    systemctl restart yadreno-vpn
    systemctl restart yadreno-vpn-web
    sleep 2

    if systemctl is-active --quiet yadreno-vpn; then
        print_ok "Бот перезапущен и работает!"
    else
        print_err "Бот не запустился после обновления"
        echo "  systemctl status yadreno-vpn"
    fi

    if systemctl is-active --quiet yadreno-vpn-web; then
        print_ok "Web admin restarted and is running"
    else
        print_err "Web admin failed to start after update"
        echo "  systemctl status yadreno-vpn-web"
    fi
}

# ============================================================
# ПУНКТ 3: ЖЁСТКАЯ ПЕРЕЗАПИСЬ (git fetch + reset)
# ============================================================
do_hard_reset() {
    print_header "⚠️  Жёсткая перезапись"
    check_runtime_environment
    check_lxc_vpn_device

    if [ ! -d "$INSTALL_DIR/.git" ]; then
        print_err "Yadreno VPN не установлен в $INSTALL_DIR"
        return 1
    fi

    echo -e "${RED}Внимание! Все локальные изменения в коде будут перезаписаны.${NC}"
    echo -e "${YELLOW}config.py и database/vpn_bot.db затронуты НЕ будут.${NC}"
    if [ "$AUTO_MODE" = "1" ]; then
        confirm="y"
    else
        read -p "Продолжить? (y/N): " confirm
    fi
    if [[ ! "$confirm" =~ ^[YyДд]$ ]]; then
        echo "Отменено."
        return 0
    fi

    cd "$INSTALL_DIR"

    # Жёсткая перезапись: config.py и database/vpn_bot.db в .gitignore — не затрагиваются
    git fetch origin -q
    local target="origin/main"
    if [ -n "$TARGET_COMMIT" ]; then
        target="$TARGET_COMMIT"
    fi
    git reset --hard "$target" -q
    git clean -fd -q
    print_ok "Код перезаписан ($target)"

    # Применяем возможные изменения systemd unit и обновляем зависимости
    setup_systemd
    update_python_deps
    run_database_migrations
    setup_initial_web_admin

    # Перезапуск
    systemctl restart yadreno-vpn
    systemctl restart yadreno-vpn-web
    sleep 2

    if systemctl is-active --quiet yadreno-vpn; then
        print_ok "Бот перезапущен и работает!"
    else
        print_err "Бот не запустился после перезаписи"
        echo "  systemctl status yadreno-vpn"
    fi

    if systemctl is-active --quiet yadreno-vpn-web; then
        print_ok "Web admin restarted and is running"
    else
        print_err "Web admin failed to start after reset"
        echo "  systemctl status yadreno-vpn-web"
    fi
}

# ============================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================
show_menu() {
    clear
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║       🌐 Yadreno VPN Manager         ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo -e "${NC}"
    echo "  1) 🚀 Установка"
    echo "  2) 🔄 Мягкое обновление (git pull)"
    echo "  3) ⚠️  Жёсткая перезапись (с GitHub)"
    echo ""
    echo "  0) Выход"
    echo ""
    read -p "  Выберите действие [0-3]: " choice

    case $choice in
        1) do_install ;;
        2) do_soft_update ;;
        3) do_hard_reset ;;
        0) echo "Пока! 👋"; exit 0 ;;
        *) echo "Неверный выбор"; return 1 ;;
    esac
}

# Проверка root-прав
if [ "$EUID" -ne 0 ]; then
    print_err "Скрипт должен быть запущен от root (sudo)"
    exit 1
fi

# Проверка на автоматический режим (передан аргумент действия)
if [ -n "$1" ]; then
    ACTION="$1"
    export AUTO_MODE="1"
    
    case "$ACTION" in
        install)
            if [ -z "$2" ] || [ -z "$3" ]; then
                print_err "Для автоматической установки требуются BOT_TOKEN и ADMIN_ID"
                echo "Использование: bash install.sh install <BOT_TOKEN> <ADMIN_ID> [WEB_ADMIN_USERNAME] [WEB_ADMIN_PASSWORD]"
                exit 1
            fi
            export BOT_TOKEN="$2"
            export ADMIN_ID="$3"
            export WEB_ADMIN_USERNAME="${4:-$WEB_ADMIN_USERNAME}"
            export WEB_ADMIN_PASSWORD="${5:-$WEB_ADMIN_PASSWORD}"
            do_install 
            ;;
        update)
            export TARGET_COMMIT="$2"
            do_soft_update 
            ;;
        reset)
            export TARGET_COMMIT="$2"
            do_hard_reset 
            ;;
        *)
            print_err "Неизвестное действие: $ACTION. Доступно: install, update, reset"
            exit 1
            ;;
    esac
    exit 0
fi

show_menu
