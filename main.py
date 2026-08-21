import tkinter as tk
from tkinter import messagebox
import threading
import asyncio
import json
import base64
import hashlib
import platform
import uuid
import subprocess
import sys
import os
import tempfile
import zipfile
import shutil
from datetime import datetime

import requests
import discord

from serverclone import Clone


# ============================================================
# НАСТРОЙКИ
# ============================================================

APP_NAME = "Katana Cloner"

# --- ВЕРСИЯ (ДОЛЖНА СОВПАДАТЬ С РЕЛИЗОМ) ---
VERSION = "1.4.7"

# --- ИМЯ .EXE ФАЙЛА (ДЛЯ ОБНОВЛЕНИЯ) ---
EXE_NAME = "KatanaCloner.exe"

# --- РЕПОЗИТОРИЙ ДЛЯ ЛИЦЕНЗИЙ ---
LIC_GITHUB_OWNER = "0xtract"
LIC_GITHUB_REPO = "katana-lic"
LIC_GITHUB_FILE = "licenses.json"
LIC_GITHUB_BRANCH = "main"
LIC_GITHUB_TOKEN = "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"

# --- РЕПОЗИТОРИЙ ДЛЯ ОБНОВЛЕНИЙ (ОТКРЫТЫЙ) ---
UPDATE_GITHUB_OWNER = "0xtract"
UPDATE_GITHUB_REPO = "auto-obnov"


# ============================================================
# ЦВЕТА
# ============================================================

BG = "#0b0d10"
PANEL = "#11151a"
PANEL2 = "#171c22"
INPUT = "#1c2229"

TEXT = "#f1f3f5"
MUTED = "#89919c"

BLUE = "#5865f2"
BLUE_HOVER = "#4752c4"

GREEN = "#43d17a"
GREEN_HOVER = "#35a862"

RED = "#ed5c5c"
RED_HOVER = "#d14a4a"

YELLOW = "#e6c45c"
ORANGE = "#f0a030"
PURPLE = "#9b59b6"
CYAN = "#00d4ff"


# ============================================================
# HWID
# ============================================================

def get_hwid():
    try:
        values = [
            platform.system(),
            platform.node(),
            platform.machine(),
            platform.processor(),
            str(uuid.getnode())
        ]

        if platform.system() == "Windows":
            try:
                result = subprocess.check_output(
                    "wmic csproduct get uuid",
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode(
                    errors="ignore"
                )
                values.append(result)
            except Exception:
                pass

        raw = "|".join(values)
        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

    except Exception:
        return None


# ============================================================
# GITHUB ДЛЯ ЛИЦЕНЗИЙ
# ============================================================

def lic_github_headers():
    return {
        "Authorization": f"Bearer {LIC_GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Katana-Cloner"
    }


def get_license_file():
    url = (
        f"https://api.github.com/repos/"
        f"{LIC_GITHUB_OWNER}/"
        f"{LIC_GITHUB_REPO}/contents/"
        f"{LIC_GITHUB_FILE}"
        f"?ref={LIC_GITHUB_BRANCH}"
    )

    try:
        response = requests.get(
            url,
            headers=lic_github_headers(),
            timeout=15
        )
    except requests.RequestException as e:
        return None, f"Ошибка подключения к GitHub: {e}"

    if response.status_code != 200:
        if response.status_code == 401:
            return None, "GitHub Token недействителен."
        if response.status_code == 403:
            return None, "GitHub Token не имеет необходимых прав."
        if response.status_code == 404:
            return None, "Репозиторий или licenses.json не найден."
        return None, f"GitHub API вернул HTTP {response.status_code}"

    try:
        data = response.json()
        content = data["content"]
        sha = data["sha"]
        content = content.replace("\n", "")
        decoded = base64.b64decode(content).decode("utf-8")
        licenses = json.loads(decoded)

        if not isinstance(licenses, dict):
            return None, "licenses.json должен содержать JSON-объект."

        return (licenses, sha), None

    except Exception as e:
        return None, f"Ошибка чтения licenses.json: {e}"


def save_license_file(licenses, sha, commit_message):
    content = json.dumps(licenses, indent=4, ensure_ascii=False)
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    url = (
        f"https://api.github.com/repos/"
        f"{LIC_GITHUB_OWNER}/"
        f"{LIC_GITHUB_REPO}/contents/"
        f"{LIC_GITHUB_FILE}"
    )

    payload = {
        "message": commit_message,
        "content": encoded,
        "sha": sha,
        "branch": LIC_GITHUB_BRANCH
    }

    try:
        response = requests.put(
            url,
            headers=lic_github_headers(),
            json=payload,
            timeout=15
        )
    except requests.RequestException as e:
        return False, str(e)

    if response.status_code not in (200, 201):
        return False, f"GitHub HTTP {response.status_code}"

    return True, None


# ============================================================
# LICENSE
# ============================================================

def check_expiration(license_data):
    expires = license_data.get("expires")
    if not expires:
        return False, "У лицензии не указан срок действия."

    try:
        expiration_date = datetime.strptime(str(expires), "%Y-%m-%d").date()
    except ValueError:
        return False, "Некорректная дата окончания лицензии."

    if datetime.now().date() > expiration_date:
        return False, "Срок действия лицензии истёк."

    return True, None


def check_license(key):
    key = key.strip()

    if not key:
        return False, "Введите лицензионный ключ.", None

    result, error = get_license_file()
    if result is None:
        return False, error, None

    licenses, sha = result

    if key not in licenses:
        return False, "Лицензионный ключ не найден.", None

    license_data = licenses[key]

    if not isinstance(license_data, dict):
        return False, "Некорректный формат лицензии.", None

    if license_data.get("active", False) is not True:
        return False, "Лицензия отключена администратором.", None

    valid, reason = check_expiration(license_data)
    if not valid:
        return False, reason, None

    current_hwid = get_hwid()
    if not current_hwid:
        return False, "Не удалось определить HWID.", None

    saved_hwid = license_data.get("hwid")

    if saved_hwid:
        if saved_hwid != current_hwid:
            return False, "Лицензия привязана к другому устройству.", None
    else:
        license_data["hwid"] = current_hwid
        license_data["last_used"] = datetime.now().strftime("%Y-%m-%d")

        success, error = save_license_file(
            licenses,
            sha,
            f"Register HWID for {key}"
        )

        if not success:
            return False, f"Не удалось зарегистрировать HWID: {error}", None

        result, error = get_license_file()
        if result is not None:
            licenses, sha = result
            license_data = licenses[key]

    license_type = str(license_data.get("type", "FREE")).upper()

    uses_left = license_data.get("uses_left")

    if uses_left is not None:
        try:
            uses_left = int(uses_left)
        except (ValueError, TypeError):
            return False, "Некорректное количество использований.", None

        if uses_left <= 0:
            return False, "Лимит использований исчерпан.", None

    if uses_left is not None:
        license_data["uses_left"] = uses_left - 1

    license_data["last_used"] = datetime.now().strftime("%Y-%m-%d")

    save_license_file(
        licenses,
        sha,
        f"Use license {key}"
    )

    return True, "Лицензия успешно активирована.", {
        "key": key,
        "type": license_type,
        "expires": license_data.get("expires"),
        "uses_left": uses_left - 1 if uses_left is not None else None,
        "hwid": current_hwid
    }


# ============================================================
# GITHUB ДЛЯ ОБНОВЛЕНИЙ (ОТКРЫТЫЙ РЕПОЗИТОРИЙ)
# ============================================================

def get_latest_release():
    """Получает информацию о последнем релизе из открытого репозитория"""
    url = f"https://api.github.com/repos/{UPDATE_GITHUB_OWNER}/{UPDATE_GITHUB_REPO}/releases/latest"
    
    try:
        response = requests.get(url, timeout=15)
    except requests.RequestException as e:
        return None, f"Ошибка подключения к GitHub: {e}"
    
    if response.status_code != 200:
        if response.status_code == 404:
            return None, "Релизов пока нет (404). Создай релиз."
        return None, f"GitHub API вернул HTTP {response.status_code}"
    
    try:
        data = response.json()
        return data, None
    except Exception as e:
        return None, f"Ошибка чтения данных релиза: {e}"


def clean_version(tag):
    version = tag.strip()
    if version.lower().startswith('v'):
        version = version[1:]
    if version.startswith('.'):
        version = version[1:]
    return version.strip()


def check_updates():
    data, error = get_latest_release()
    
    if data is None:
        return False, error, None
    
    tag_name = data.get("tag_name", "")
    latest_version = clean_version(tag_name)
    
    if not latest_version:
        return False, "В релизе не указана версия.", None
    
    if compare_versions(latest_version, VERSION) > 0:
        return True, f"Доступна версия {latest_version}", {
            "version": latest_version,
            "url": data.get("zipball_url"),
            "body": data.get("body", ""),
            "assets": data.get("assets", []),
            "created_at": data.get("created_at", "")
        }
    else:
        return False, "У вас последняя версия.", None


def compare_versions(v1, v2):
    if not v1 or not v2:
        return 0
        
    try:
        v1_parts = [int(x) for x in v1.split('.')]
        v2_parts = [int(x) for x in v2.split('.')]
    except ValueError:
        return 0
        
    while len(v1_parts) < len(v2_parts):
        v1_parts.append(0)
    while len(v2_parts) < len(v1_parts):
        v2_parts.append(0)
        
    for i in range(len(v1_parts)):
        if v1_parts[i] > v2_parts[i]:
            return 1
        if v1_parts[i] < v2_parts[i]:
            return -1
    return 0


# ============================================================
# ЗАГРУЗКА И УСТАНОВКА ОБНОВЛЕНИЯ
# ============================================================

def download_and_install_update(update_info, logger=None):
    try:
        if logger:
            logger("[UPDATER] Загрузка обновления...")
        
        # Проверяем, запущено ли как .exe
        is_exe = getattr(sys, 'frozen', False)
        
        if is_exe:
            # === ОБНОВЛЕНИЕ ДЛЯ .EXE ===
            if logger:
                logger("[UPDATER] Обновление для .exe")
            
            # Ищем .exe файл в релизе
            exe_url = None
            for asset in update_info.get("assets", []):
                asset_name = asset.get("name", "")
                if asset_name.endswith(".exe"):
                    exe_url = asset.get("browser_download_url")
                    break
            
            if not exe_url:
                if logger:
                    logger("[UPDATER] .exe файл не найден в релизе!")
                return False, ".exe файл не найден в релизе"
            
            if logger:
                logger(f"[UPDATER] Найден .exe: {exe_url}")
            
            # СКАЧИВАЕМ БЕЗ ТОКЕНА (ОТКРЫТЫЙ РЕПОЗИТОРИЙ)
            response = requests.get(exe_url, stream=True, timeout=60)
            
            if response.status_code != 200:
                if logger:
                    logger(f"[UPDATER] Ошибка скачивания: HTTP {response.status_code}")
                return False, f"Ошибка скачивания: HTTP {response.status_code}"
            
            # Получаем путь к текущему .exe
            current_exe = sys.executable
            current_dir = os.path.dirname(current_exe)
            temp_exe = os.path.join(current_dir, f"update_temp_{int(datetime.now().timestamp())}.exe")
            
            if logger:
                logger(f"[UPDATER] Сохранение в: {temp_exe}")
            
            # Сохраняем новый .exe
            with open(temp_exe, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if logger:
                logger("[UPDATER] Новый .exe скачан")
            
            # Создаём bat-файл для замены .exe
            bat_path = os.path.join(current_dir, "update.bat")
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(f"""@echo off
chcp 65001 >nul
timeout /t 2 /nobreak >nul
echo Обновление Katana Cloner...
copy /Y "{temp_exe}" "{current_exe}"
if errorlevel 1 (
    echo Ошибка копирования! Запустите от имени администратора.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit
)
echo Обновление успешно установлено!
echo Запуск Katana Cloner...
start "" "{current_exe}"
del "%~f0"
""")
            
            if logger:
                logger("[UPDATER] Запуск обновления...")
            
            # Запускаем bat-файл
            subprocess.Popen(
                bat_path,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            # Закрываем текущее приложение
            sys.exit(0)
            
        else:
            # === ОБНОВЛЕНИЕ ДЛЯ .PY ===
            if logger:
                logger("[UPDATER] Обновление для .py")
            
            response = requests.get(
                update_info["url"],
                stream=True,
                timeout=60
            )
            
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "update.zip")
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if logger:
                logger("[UPDATER] Распаковка...")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            main_file = None
            for root, dirs, files in os.walk(temp_dir):
                if "main.py" in files:
                    main_file = os.path.join(root, "main.py")
                    break
            
            if not main_file:
                if logger:
                    logger("[UPDATER] Файл main.py не найден!")
                return False, "Файл main.py не найден в архиве"
            
            current_dir = os.path.dirname(sys.argv[0])
            target_file = os.path.join(current_dir, "main.py")
            
            shutil.copy2(main_file, target_file)
            
            if logger:
                logger("[UPDATER] Обновление установлено!")
            
            return True, None
        
    except Exception as e:
        return False, f"Ошибка обновления: {e}"


# ============================================================
# КЛАСС ДЛЯ УПРАВЛЕНИЯ ОБНОВЛЕНИЯМИ
# ============================================================

class UpdateWorker:
    def __init__(self, logger, root, callback=None):
        self.logger = logger
        self.root = root
        self.callback = callback
        self.running = False
        
    def log(self, text):
        if self.logger:
            self.logger(text)
    
    def check_in_thread(self):
        if self.running:
            return
            
        self.running = True
        self.log("[UPDATER] Проверка обновлений...")
        
        def worker():
            try:
                success, message, info = check_updates()
                
                if success:
                    self.root.after(0, lambda: self.on_update_available(info))
                else:
                    self.root.after(0, lambda: self.on_no_update(message))
                    
            except Exception as e:
                self.log(f"[UPDATER] Ошибка: {e}")
                self.root.after(0, self.on_error)
            finally:
                self.running = False
        
        threading.Thread(target=worker, daemon=True).start()
    
    def on_update_available(self, info):
        self.log(f"[UPDATER] Доступна версия {info['version']}")
        if self.callback:
            self.callback("available", info)
    
    def on_no_update(self, message):
        self.log(f"[UPDATER] {message}")
        if self.callback:
            self.callback("up_to_date", None)
    
    def on_error(self):
        self.log("[UPDATER] Не удалось проверить обновления")
        if self.callback:
            self.callback("error", None)
    
    def install_update(self, update_info):
        self.log("[UPDATER] Установка обновления...")
        
        def worker():
            success, error = download_and_install_update(update_info, self.log)
            
            if success:
                self.root.after(1000, self.restart_app)
            else:
                self.log(f"[UPDATER] {error}")
                self.root.after(0, lambda: messagebox.showerror("Ошибка", error))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def restart_app(self):
        self.log("[UPDATER] Перезапуск...")
        
        is_exe = getattr(sys, 'frozen', False)
        
        if is_exe:
            subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable, sys.argv[0]])
        
        self.root.destroy()
        sys.exit(0)


# ============================================================
# UPDATE WINDOW
# ============================================================

class UpdateWindow:
    def __init__(self, parent, update_info, on_confirm, on_cancel):
        self.parent = parent
        self.update_info = update_info
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        
        self.window = tk.Toplevel(parent)
        self.window.title("Обновление Katana Cloner")
        self.window.geometry("680x600")
        self.window.resizable(False, False)
        self.window.configure(bg=BG)
        
        self.window.overrideredirect(True)
        
        self.create_custom_titlebar()
        
        self.center_window()
        
        self.window.transient(parent)
        self.window.grab_set()
        self.window.focus_force()
        
        self.build()
        
        self.window.bind("<Escape>", lambda e: self.cancel())
        self.window.bind("<Return>", lambda e: self.confirm())
    
    def create_custom_titlebar(self):
        self.title_bar = tk.Frame(self.window, bg=PANEL2, height=42)
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)
        
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.on_move)
        
        tk.Label(
            self.title_bar,
            text="⚔️ Katana Cloner",
            bg=PANEL2,
            fg=TEXT,
            font=("Segoe UI", 12, "bold")
        ).pack(side="left", padx=18, pady=8)
        
        self.close_btn = tk.Button(
            self.title_bar,
            text="✕",
            command=self.cancel,
            bg=PANEL2,
            fg=MUTED,
            activebackground=RED,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 14, "bold"),
            cursor="hand2",
            width=4
        )
        self.close_btn.pack(side="right", padx=6, pady=4)
        
        self.main_frame = tk.Frame(self.window, bg=BG)
        self.main_frame.pack(fill="both", expand=True, padx=40, pady=25)
    
    def start_move(self, event):
        self.x = event.x
        self.y = event.y
    
    def on_move(self, event):
        x = self.window.winfo_x() + event.x - self.x
        y = self.window.winfo_y() + event.y - self.y
        self.window.geometry(f"+{x}+{y}")
    
    def center_window(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
    
    def build(self):
        icon_frame = tk.Frame(self.main_frame, bg=BG)
        icon_frame.pack(pady=(0, 8))
        
        tk.Label(
            icon_frame,
            text="🔄",
            bg=BG,
            fg=BLUE,
            font=("Segoe UI", 46)
        ).pack()
        
        tk.Label(
            self.main_frame,
            text="ДОСТУПНО ОБНОВЛЕНИЕ!",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 20, "bold")
        ).pack()
        
        tk.Label(
            self.main_frame,
            text="Для продолжения работы необходимо обновиться",
            bg=BG,
            fg=YELLOW,
            font=("Segoe UI", 12)
        ).pack(pady=(5, 18))
        
        version_frame = tk.Frame(self.main_frame, bg=PANEL)
        version_frame.pack(fill="x", pady=(0, 18), ipady=14)
        
        tk.Label(
            version_frame,
            text=f"Новая версия: v{self.update_info['version']}",
            bg=PANEL,
            fg=BLUE,
            font=("Segoe UI", 26, "bold")
        ).pack()
        
        body_frame = tk.Frame(self.main_frame, bg=PANEL2)
        body_frame.pack(fill="both", expand=True, pady=(0, 18))
        
        body_text = self.update_info.get('body', '')
        
        text_widget = tk.Text(
            body_frame,
            bg=PANEL2,
            fg=TEXT,
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            wrap="word",
            height=9
        )
        text_widget.pack(fill="both", expand=True, padx=15, pady=15)
        
        if body_text:
            formatted_text = body_text.replace('**', '')
            formatted_text = formatted_text.replace('•', '▸')
            formatted_text = formatted_text.replace('✦', '★')
            text_widget.insert("1.0", formatted_text)
        else:
            text_widget.insert("1.0", "Описание обновления отсутствует.")
        
        text_widget.config(state="disabled")
        
        buttons_frame = tk.Frame(self.main_frame, bg=BG)
        buttons_frame.pack(fill="x", pady=(0, 5))
        
        self.confirm_btn = tk.Button(
            buttons_frame,
            text="⬇ ОБНОВИТЬ",
            command=self.confirm,
            bg=BLUE,
            fg="white",
            activebackground=BLUE_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 14, "bold"),
            cursor="hand2",
            height=2,
            width=25
        )
        self.confirm_btn.pack(side="left", padx=(0, 10), ipady=14, expand=True, fill="x")
        
        self.cancel_btn = tk.Button(
            buttons_frame,
            text="✕ ЗАКРЫТЬ",
            command=self.cancel,
            bg=PANEL2,
            fg=MUTED,
            activebackground=RED,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 14, "bold"),
            cursor="hand2",
            height=2,
            width=25
        )
        self.cancel_btn.pack(side="left", ipady=14, expand=True, fill="x")
        
        tk.Label(
            self.main_frame,
            text="Нажмите 'Обновить' для установки или 'Закрыть' для выхода",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(pady=(10, 0))
    
    def confirm(self):
        self.window.destroy()
        if self.on_confirm:
            self.on_confirm()
    
    def cancel(self):
        self.window.destroy()
        if self.on_cancel:
            self.on_cancel()


# ============================================================
# DISCORD CLIENT
# ============================================================

class DiscordCloner(discord.Client):
    def __init__(self, source_id, target_id, logger, stop_event):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        self.source_id = source_id
        self.target_id = target_id
        self.logger = logger
        self.stop_event = stop_event

    def log(self, text):
        self.logger(text)

    async def on_ready(self):
        self.log(f"Авторизация: {self.user}")

        if self.stop_event.is_set():
            self.log("Операция остановлена.")
            await self.close()
            return

        guild_from = self.get_guild(self.source_id)
        guild_to = self.get_guild(self.target_id)

        if guild_from is None:
            self.log("ОШИБКА: исходный сервер не найден.")
            await self.close()
            return

        if guild_to is None:
            self.log("ОШИБКА: сервер назначения не найден.")
            await self.close()
            return

        self.log(f"Источник: {guild_from.name}")
        self.log(f"Назначение: {guild_to.name}")
        self.log("Начинаю клонирование...")

        try:
            if self.stop_event.is_set():
                await self.close()
                return

            self.log("Изменение параметров сервера...")
            await Clone.guild_edit(guild_to, guild_from)

            if self.stop_event.is_set():
                await self.close()
                return

            self.log("Удаление старых ролей...")
            await Clone.roles_delete(guild_to)

            if self.stop_event.is_set():
                await self.close()
                return

            self.log("Удаление старых каналов...")
            await Clone.channels_delete(guild_to)

            if self.stop_event.is_set():
                await self.close()
                return

            self.log("Создание ролей...")
            await Clone.roles_create(guild_to, guild_from)

            if self.stop_event.is_set():
                await self.close()
                return

            self.log("Создание категорий...")
            await Clone.categories_create(guild_to, guild_from)

            if self.stop_event.is_set():
                await self.close()
                return

            self.log("Создание каналов...")
            await Clone.channels_create(guild_to, guild_from)

            self.log("✓ Клонирование завершено.")

        except discord.Forbidden:
            self.log("ОШИБКА: недостаточно прав.")
        except discord.HTTPException as e:
            self.log(f"Discord API ошибка: {e}")
        except Exception as e:
            self.log(f"Ошибка: {e}")

        await asyncio.sleep(2)
        await self.close()


# ============================================================
# LICENSE WINDOW
# ============================================================

class LicenseWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Katana Cloner — License")
        self.root.geometry("520x420")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.build()

    def build(self):
        title = tk.Label(self.root, text="KATANA", bg=BG, fg=TEXT, font=("Segoe UI", 30, "bold"))
        title.pack(pady=(35, 0))

        subtitle = tk.Label(self.root, text="CLONER", bg=BG, fg=BLUE, font=("Segoe UI", 14, "bold"))
        subtitle.pack()

        text = tk.Label(self.root, text="Введите лицензионный ключ", bg=BG, fg=MUTED, font=("Segoe UI", 10))
        text.pack(pady=(28, 12))

        entry_frame = tk.Frame(self.root, bg=BG)
        entry_frame.pack(padx=50, fill="x", pady=(0, 5))

        self.entry = tk.Entry(
            entry_frame,
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 12),
            justify="left"
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=12)

        self.paste_button = tk.Button(
            entry_frame,
            text="📋",
            command=self.paste_from_clipboard,
            bg=BLUE,
            fg="white",
            activebackground=BLUE_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 16),
            cursor="hand2",
            width=3
        )
        self.paste_button.pack(side="right", padx=(6, 0), ipady=9)

        self.entry.focus()

        self.status = tk.Label(self.root, text="Ожидание активации", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.status.pack(pady=(15, 15))

        self.button = tk.Button(
            self.root,
            text="АКТИВИРОВАТЬ",
            command=self.activate,
            bg=BLUE,
            fg="white",
            activebackground=BLUE_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
            width=20
        )
        self.button.pack(ipadx=10, ipady=12)

        self.root.bind("<Return>", lambda event: self.activate())
        self.root.bind("<Control-v>", lambda event: self.paste_from_clipboard())
        self.root.bind("<Control-V>", lambda event: self.paste_from_clipboard())

    def paste_from_clipboard(self):
        try:
            clipboard_text = self.root.clipboard_get()
            if clipboard_text:
                self.entry.delete(0, tk.END)
                self.entry.insert(0, clipboard_text.strip())
                self.status.config(text="✓ Вставлено из буфера обмена", fg=GREEN)
                self.root.after(1500, lambda: self.status.config(text="Ожидание активации", fg=MUTED))
        except tk.TclError:
            self.status.config(text="Буфер обмена пуст", fg=RED)
            self.root.after(1500, lambda: self.status.config(text="Ожидание активации", fg=MUTED))

    def activate(self):
        key = self.entry.get().strip()
        if not key:
            self.status.config(text="Введите ключ.", fg=RED)
            return

        self.button.config(state="disabled", text="ПРОВЕРКА...")
        self.status.config(text="Подключение к GitHub...", fg=MUTED)

        threading.Thread(target=self.worker, args=(key,), daemon=True).start()

    def worker(self, key):
        success, message, info = check_license(key)
        self.root.after(0, self.finish, success, message, info)

    def finish(self, success, message, info):
        if not success:
            self.status.config(text=message, fg=RED)
            self.button.config(state="normal", text="АКТИВИРОВАТЬ")
            return

        self.root.destroy()
        MainWindow(info).run()

    def run(self):
        self.root.mainloop()


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow:
    def __init__(self, license_info):
        self.license_info = license_info
        self.discord_client = None
        self.stop_event = threading.Event()
        self.running = False
        self.license_window_open = False
        self.update_info = None

        self.root = tk.Tk()
        self.root.title("Katana Cloner")
        self.root.geometry("1050x650")
        self.root.minsize(950, 600)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.build()

    def build(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 10))

        title_frame = tk.Frame(header, bg=BG)
        title_frame.pack(side="left")

        tk.Label(title_frame, text="KATANA", bg=BG, fg=TEXT, font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(title_frame, text=" CLONER", bg=BG, fg=BLUE, font=("Segoe UI", 13, "bold")).pack(side="left", pady=(8, 0))

        # --- КНОПКА ОБНОВЛЕНИЯ (СКРЫТА ПО УМОЛЧАНИЮ) ---
        self.update_frame = tk.Frame(header, bg=BG)
        
        self.update_button = tk.Button(
            self.update_frame,
            text="⬇ ОБНОВИТЬ",
            command=self.start_update,
            bg=BLUE,
            fg="white",
            activebackground=BLUE_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2"
        )
        self.update_button.pack(ipadx=10, ipady=5)

        # --- КНОПКА ЛИЦЕНЗИИ ---
        self.license_button = tk.Button(
            header,
            text="ЛИЦЕНЗИЯ",
            command=self.show_license,
            bg=PANEL2,
            fg=TEXT,
            activebackground=INPUT,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        )
        self.license_button.pack(side="right", ipadx=14, ipady=7)

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=28, pady=10)

        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        right = tk.Frame(content, bg=PANEL)
        right.pack(side="right", fill="both", expand=True, padx=(12, 0))

        self.build_left(left)
        self.build_terminal(right)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=28, pady=(0, 10))
        tk.Label(
            footer,
            text="Developer: katanov_soulchik  |  Script owner: sakuralol.121_50087",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8),
            justify="center"
        ).pack(side="bottom", pady=5)

        # --- ЗАПУСКАЕМ ПРОВЕРКУ ОБНОВЛЕНИЙ ---
        self.update_worker = UpdateWorker(
            logger=self.log,
            root=self.root,
            callback=self.on_update_result
        )
        self.root.after(3000, self.update_worker.check_in_thread)

    def on_update_result(self, status, info):
        if status == "available":
            self.update_frame.pack(side="right", padx=(0, 5))
            self.update_button.config(text=f"⬇ ОБНОВИТЬ v{info['version']}")
            self.update_info = info
            self.root.after(500, self.start_update)
            
        elif status == "up_to_date":
            self.update_frame.pack_forget()
            
        else:
            self.update_frame.pack_forget()

    def start_update(self):
        if not self.update_info:
            return
        
        def on_confirm():
            self.update_button.config(state="disabled", text="⏳ ЗАГРУЗКА...")
            self.update_worker.install_update(self.update_info)
        
        def on_cancel():
            self.log("[SYSTEM] Обновление отклонено. Выход...")
            self.root.after(500, self.root.destroy)
        
        UpdateWindow(
            parent=self.root,
            update_info=self.update_info,
            on_confirm=on_confirm,
            on_cancel=on_cancel
        )

    def build_left(self, parent):
        card = tk.Frame(parent, bg=PANEL)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="Настройки подключения", bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=25, pady=(25, 20)
        )

        self.create_label(card, "Токен аккаунта Discord")
        self.token_entry = self.create_entry(card, show="●")

        self.create_label(card, "ID исходного сервера")
        self.source_entry = self.create_entry(card)

        self.create_label(card, "ID сервера назначения")
        self.target_entry = self.create_entry(card)

        status_frame = tk.Frame(card, bg=PANEL2)
        status_frame.pack(fill="x", padx=25, pady=(22, 10))

        self.status_dot = tk.Label(status_frame, text="●", bg=PANEL2, fg=GREEN, font=("Segoe UI", 13))
        self.status_dot.pack(side="left", padx=(12, 7))

        self.status_text = tk.Label(status_frame, text="Готов к работе", bg=PANEL2, fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.status_text.pack(side="left", pady=10)

        buttons = tk.Frame(card, bg=PANEL)
        buttons.pack(fill="x", padx=25, pady=20)

        self.start_button = tk.Button(
            buttons,
            text="НАЧАТЬ",
            command=self.start_clone,
            bg=BLUE,
            fg="white",
            activebackground=BLUE_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        self.start_button.pack(side="left", fill="x", expand=True, ipadx=10, ipady=11)

        self.stop_button = tk.Button(
            buttons,
            text="ОСТАНОВИТЬ",
            command=self.stop_clone,
            bg="#292f36",
            fg="#aaaaaa",
            activebackground="#383f47",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            state="disabled",
            cursor="hand2"
        )
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(10, 0), ipadx=10, ipady=11)

        tk.Label(
            card,
            text="Используется токен аккаунта Discord.\nАккаунт должен иметь права на обоих серверах.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
            wraplength=400,
            justify="left"
        ).pack(anchor="w", padx=25, pady=(5, 20))

    def build_terminal(self, parent):
        tk.Label(parent, text="Терминал", bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=20, pady=(20, 10)
        )

        self.log_box = tk.Text(
            parent,
            bg="#080a0c",
            fg="#cfd5dc",
            insertbackground="#ffffff",
            selectbackground="#303741",
            relief="flat",
            bd=0,
            font=("Consolas", 9),
            state="disabled",
            wrap="word"
        )
        self.log_box.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.log("[SYSTEM] Katana Cloner запущен.")
        self.log("[SYSTEM] Ожидание запуска.")

    def create_label(self, parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=25, pady=(7, 5)
        )

    def create_entry(self, parent, show=None):
        entry = tk.Entry(
            parent,
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
            show=show
        )
        entry.pack(fill="x", padx=25, ipady=10)
        return entry

    def log(self, text):
        def write():
            self.log_box.config(state="normal")
            self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")

        self.root.after(0, write)

    def show_license(self):
        if self.license_window_open:
            return

        self.license_window_open = True

        info = tk.Toplevel(self.root)
        info.title("Информация о лицензии")
        info.geometry("430x390")
        info.resizable(False, False)
        info.configure(bg=BG)

        def on_close():
            self.license_window_open = False
            info.destroy()

        info.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(info, text="ЛИЦЕНЗИЯ", bg=BG, fg=TEXT, font=("Segoe UI", 20, "bold")).pack(pady=(30, 5))
        tk.Label(info, text="Информация об активной лицензии", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 25))

        data = [
            ("Статус", "АКТИВНА", GREEN),
            ("Тип", self.license_info.get("type", "UNKNOWN"), CYAN),
            ("Дата окончания", self.license_info.get("expires", "—"), YELLOW),
            ("Использований", "∞" if self.license_info.get("uses_left") is None else str(self.license_info.get("uses_left")), ORANGE),
        ]

        for name, value, color in data:
            row = tk.Frame(info, bg=PANEL)
            row.pack(fill="x", padx=30, pady=4)

            tk.Label(row, text=name, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=12, pady=10)
            tk.Label(row, text=value, bg=PANEL, fg=color, font=("Segoe UI", 9, "bold")).pack(side="right", padx=12)

        hwid = self.license_info.get("hwid", "")
        tk.Label(info, text="HWID", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(pady=(18, 2))
        tk.Label(info, text=hwid, bg=BG, fg="#666f79", font=("Consolas", 7)).pack(padx=20)

    def start_clone(self):
        if self.running:
            return

        token = self.token_entry.get().strip()
        source = self.source_entry.get().strip()
        target = self.target_entry.get().strip()

        if not token:
            messagebox.showerror("Ошибка", "Введите токен аккаунта Discord.")
            return

        if not source.isdigit():
            messagebox.showerror("Ошибка", "ID исходного сервера должен содержать только цифры.")
            return

        if not target.isdigit():
            messagebox.showerror("Ошибка", "ID сервера назначения должен содержать только цифры.")
            return

        if source == target:
            messagebox.showerror("Ошибка", "Серверы не должны совпадать.")
            return

        self.running = True
        self.stop_event.clear()

        self.start_button.config(state="disabled", text="РАБОТАЕТ...")
        self.stop_button.config(state="normal", bg=RED, fg="white")
        self.status_dot.config(fg=RED)
        self.status_text.config(text="Клонирование выполняется...", fg=RED)

        self.log("[SYSTEM] Запуск Discord...")

        threading.Thread(
            target=self.discord_worker,
            args=(token, int(source), int(target)),
            daemon=True
        ).start()

    def discord_worker(self, token, source, target):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.discord_client = DiscordCloner(
                source,
                target,
                self.log,
                self.stop_event
            )

            loop.run_until_complete(
                self.discord_client.start(token, bot=False)
            )

        except discord.LoginFailure:
            self.log("[ERROR] Discord отклонил токен.")
        except Exception as e:
            self.log(f"[ERROR] {e}")
        finally:
            try:
                if self.discord_client and not self.discord_client.is_closed():
                    loop = self.discord_client.loop
                    if loop and loop.is_running():
                        loop.run_until_complete(self.discord_client.close())
            except:
                pass

            self.discord_client = None
            self.root.after(0, self.clone_finished)

    def stop_clone(self):
        if not self.running:
            return

        self.log("[SYSTEM] Запрошена остановка...")
        self.stop_event.set()

        self.stop_button.config(state="disabled", text="ОСТАНОВКА...")
        self.status_text.config(text="Остановка...", fg=YELLOW)

        if self.discord_client is not None:
            try:
                loop = self.discord_client.loop
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.discord_client.close(),
                        loop
                    )
                else:
                    self.discord_client.close()
            except Exception:
                try:
                    if self.discord_client:
                        self.discord_client.close()
                except:
                    pass

    def clone_finished(self):
        self.running = False

        self.start_button.config(state="normal", text="НАЧАТЬ")
        self.stop_button.config(state="disabled", text="ОСТАНОВИТЬ", bg="#292f36", fg="#aaaaaa")

        if self.stop_event.is_set():
            self.status_dot.config(fg=YELLOW)
            self.status_text.config(text="Остановлено", fg=YELLOW)
            self.log("[SYSTEM] Операция остановлена.")
        else:
            self.status_dot.config(fg=GREEN)
            self.status_text.config(text="Готов к работе", fg=GREEN)
            self.log("[SYSTEM] Клонирование завершено. Ожидание новых команд.")

    def close(self):
        if self.running:
            answer = messagebox.askyesno(
                "Выход",
                "Клонирование ещё выполняется.\nОстановить операцию и выйти?"
            )
            if not answer:
                return
            self.stop_clone()

        self.root.after(300, self.root.destroy)

    def run(self):
        self.root.mainloop()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    try:
        LicenseWindow().run()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        input("Нажмите Enter для выхода...")
