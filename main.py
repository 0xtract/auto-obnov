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
from datetime import datetime

import requests
import discord

from serverclone import Clone


# ============================================================
# НАСТРОЙКИ
# ============================================================

APP_NAME = "Katana Cloner"

GITHUB_OWNER = "0xtract"
GITHUB_REPO = "katana-lic"
GITHUB_FILE = "licenses.json"
GITHUB_BRANCH = "main"

GITHUB_TOKEN = "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"


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
# GITHUB
# ============================================================

def github_headers():

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Katana-Cloner"
    }


def get_license_file():

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/contents/"
        f"{GITHUB_FILE}"
        f"?ref={GITHUB_BRANCH}"
    )

    try:

        response = requests.get(
            url,
            headers=github_headers(),
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

            return None, (
                "Репозиторий или licenses.json не найден."
            )

        return None, (
            f"GitHub API вернул HTTP "
            f"{response.status_code}"
        )

    try:

        data = response.json()

        content = data["content"]
        sha = data["sha"]

        content = content.replace("\n", "")

        decoded = base64.b64decode(
            content
        ).decode("utf-8")

        licenses = json.loads(decoded)

        if not isinstance(licenses, dict):

            return None, (
                "licenses.json должен содержать JSON-объект."
            )

        return (licenses, sha), None

    except Exception as e:

        return None, (
            f"Ошибка чтения licenses.json: {e}"
        )


def save_license_file(
    licenses,
    sha,
    commit_message
):

    content = json.dumps(
        licenses,
        indent=4,
        ensure_ascii=False
    )

    encoded = base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/contents/"
        f"{GITHUB_FILE}"
    )

    payload = {
        "message": commit_message,
        "content": encoded,
        "sha": sha,
        "branch": GITHUB_BRANCH
    }

    try:

        response = requests.put(
            url,
            headers=github_headers(),
            json=payload,
            timeout=15
        )

    except requests.RequestException as e:

        return False, str(e)

    if response.status_code not in (200, 201):

        return False, (
            f"GitHub HTTP {response.status_code}"
        )

    return True, None


# ============================================================
# LICENSE
# ============================================================

def check_expiration(license_data):

    expires = license_data.get("expires")

    if not expires:

        return False, (
            "У лицензии не указан срок действия."
        )

    try:

        expiration_date = datetime.strptime(
            str(expires),
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return False, (
            "Некорректная дата окончания лицензии."
        )

    if datetime.now().date() > expiration_date:

        return False, (
            "Срок действия лицензии истёк."
        )

    return True, None


def check_license(key):

    key = key.strip()

    if not key:

        return False, (
            "Введите лицензионный ключ."
        ), None

    result, error = get_license_file()

    if result is None:

        return False, error, None

    licenses, sha = result

    if key not in licenses:

        return False, (
            "Лицензионный ключ не найден."
        ), None

    license_data = licenses[key]

    if not isinstance(
        license_data,
        dict
    ):

        return False, (
            "Некорректный формат лицензии."
        ), None

    if license_data.get(
        "active",
        False
    ) is not True:

        return False, (
            "Лицензия отключена администратором."
        ), None

    valid, reason = check_expiration(
        license_data
    )

    if not valid:

        return False, reason, None

    current_hwid = get_hwid()

    if not current_hwid:

        return False, (
            "Не удалось определить HWID."
        ), None

    saved_hwid = license_data.get(
        "hwid"
    )

    if saved_hwid:

        if saved_hwid != current_hwid:

            return False, (
                "Лицензия привязана к другому устройству."
            ), None

    else:

        license_data["hwid"] = current_hwid

        license_data["last_used"] = (
            datetime.now().strftime("%Y-%m-%d")
        )

        success, error = save_license_file(
            licenses,
            sha,
            f"Register HWID for {key}"
        )

        if not success:

            return False, (
                f"Не удалось зарегистрировать HWID: {error}"
            ), None

        result, error = get_license_file()

        if result is not None:

            licenses, sha = result
            license_data = licenses[key]

    license_type = str(
        license_data.get(
            "type",
            "FREE"
        )
    ).upper()

    uses_left = license_data.get(
        "uses_left"
    )

    if uses_left is not None:

        try:

            uses_left = int(
                uses_left
            )

        except (
            ValueError,
            TypeError
        ):

            return False, (
                "Некорректное количество использований."
            ), None

        if uses_left <= 0:

            return False, (
                "Лимит использований исчерпан."
            ), None

    if uses_left is not None:

        license_data["uses_left"] = (
            uses_left - 1
        )

    license_data["last_used"] = (
        datetime.now().strftime("%Y-%m-%d")
    )

    save_license_file(
        licenses,
        sha,
        f"Use license {key}"
    )

    return True, (
        "Лицензия успешно активирована."
    ), {
        "key": key,
        "type": license_type,
        "expires": license_data.get(
            "expires"
        ),
        "uses_left": (
            uses_left - 1
            if uses_left is not None
            else None
        ),
        "hwid": current_hwid
    }


# ============================================================
# DISCORD CLIENT
# ============================================================

class DiscordCloner(discord.Client):

    def __init__(
        self,
        source_id,
        target_id,
        logger,
        stop_event
    ):

        intents = discord.Intents.all()
        
        super().__init__(
            intents=intents
        )

        self.source_id = source_id
        self.target_id = target_id

        self.logger = logger
        self.stop_event = stop_event

    def log(self, text):

        self.logger(text)

    async def on_ready(self):

        self.log(
            f"Авторизация: {self.user}"
        )

        if self.stop_event.is_set():

            self.log(
                "Операция остановлена."
            )

            await self.close()
            return

        guild_from = self.get_guild(
            self.source_id
        )

        guild_to = self.get_guild(
            self.target_id
        )

        if guild_from is None:

            self.log(
                "ОШИБКА: исходный сервер не найден."
            )

            await self.close()
            return

        if guild_to is None:

            self.log(
                "ОШИБКА: сервер назначения не найден."
            )

            await self.close()
            return

        self.log(
            f"Источник: {guild_from.name}"
        )

        self.log(
            f"Назначение: {guild_to.name}"
        )

        self.log(
            "Начинаю клонирование..."
        )

        try:

            if self.stop_event.is_set():
                await self.close()
                return

            self.log(
                "Изменение параметров сервера..."
            )

            await Clone.guild_edit(
                guild_to,
                guild_from
            )

            if self.stop_event.is_set():
                await self.close()
                return

            self.log(
                "Удаление старых ролей..."
            )

            await Clone.roles_delete(
                guild_to
            )

            if self.stop_event.is_set():
                await self.close()
                return

            self.log(
                "Удаление старых каналов..."
            )

            await Clone.channels_delete(
                guild_to
            )

            if self.stop_event.is_set():
                await self.close()
                return

            self.log(
                "Создание ролей..."
            )

            await Clone.roles_create(
                guild_to,
                guild_from
            )

            if self.stop_event.is_set():
                await self.close()
                return

            self.log(
                "Создание категорий..."
            )

            await Clone.categories_create(
                guild_to,
                guild_from
            )

            if self.stop_event.is_set():
                await self.close()
                return

            self.log(
                "Создание каналов..."
            )

            await Clone.channels_create(
                guild_to,
                guild_from
            )

            self.log(
                "✓ Клонирование завершено."
            )

        except discord.Forbidden:

            self.log(
                "ОШИБКА: недостаточно прав."
            )

        except discord.HTTPException as e:

            self.log(
                f"Discord API ошибка: {e}"
            )

        except Exception as e:

            self.log(
                f"Ошибка: {e}"
            )

        await asyncio.sleep(2)

        await self.close()


# ============================================================
# LICENSE WINDOW - НОВЫЙ ДИЗАЙН
# ============================================================

class LicenseWindow:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            "Katana Cloner — License"
        )

        # Увеличиваем окно для гармоничного размещения
        self.root.geometry(
            "520x420"
        )

        self.root.resizable(
            False,
            False
        )

        self.root.configure(
            bg=BG
        )

        self.build()

    def build(self):

        # Заголовок KATANA
        title = tk.Label(
            self.root,
            text="KATANA",
            bg=BG,
            fg=TEXT,
            font=(
                "Segoe UI",
                30,
                "bold"
            )
        )

        title.pack(
            pady=(35, 0)
        )

        # Подзаголовок CLONER синим
        subtitle = tk.Label(
            self.root,
            text="CLONER",
            bg=BG,
            fg=BLUE,
            font=(
                "Segoe UI",
                14,
                "bold"
            )
        )

        subtitle.pack()

        # Текст "Введите лицензионный ключ"
        text = tk.Label(
            self.root,
            text="Введите лицензионный ключ",
            bg=BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                10
            )
        )

        text.pack(
            pady=(28, 12)
        )

        # Контейнер для поля ввода и кнопки вставки
        entry_frame = tk.Frame(
            self.root,
            bg=BG
        )
        
        entry_frame.pack(
            padx=50,
            fill="x",
            pady=(0, 5)
        )

        # Поле ввода - гармоничного размера
        self.entry = tk.Entry(
            entry_frame,
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=(
                "Segoe UI",
                12
            ),
            justify="left"
        )

        self.entry.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=12
        )

        # Кнопка вставки из буфера обмена - синяя
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
            font=(
                "Segoe UI",
                16
            ),
            cursor="hand2",
            width=3
        )
        
        self.paste_button.pack(
            side="right",
            padx=(6, 0),
            ipady=9
        )

        # Устанавливаем фокус на поле ввода
        self.entry.focus()

        # Статус
        self.status = tk.Label(
            self.root,
            text="Ожидание активации",
            bg=BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                9
            )
        )

        self.status.pack(
            pady=(15, 15)
        )

        # Кнопка активации - синяя, гармоничного размера
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
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            cursor="hand2",
            width=20
        )

        self.button.pack(
            ipadx=10,
            ipady=12
        )

        # Горячие клавиши
        self.root.bind(
            "<Return>",
            lambda event: self.activate()
        )
        
        # Привязываем Ctrl+V для вставки независимо от раскладки
        self.root.bind(
            "<Control-v>",
            lambda event: self.paste_from_clipboard()
        )
        
        self.root.bind(
            "<Control-V>",
            lambda event: self.paste_from_clipboard()
        )

    def paste_from_clipboard(self):
        
        try:
            # Получаем текст из буфера обмена
            clipboard_text = self.root.clipboard_get()
            
            if clipboard_text:
                # Очищаем поле и вставляем текст
                self.entry.delete(0, tk.END)
                self.entry.insert(0, clipboard_text.strip())
                
                # Меняем цвет статуса на зелёный
                self.status.config(
                    text="✓ Вставлено из буфера обмена",
                    fg=GREEN
                )
                
                # Возвращаем стандартный текст через 1.5 секунды
                self.root.after(
                    1500,
                    lambda: self.status.config(
                        text="Ожидание активации",
                        fg=MUTED
                    )
                )
                
        except tk.TclError:
            # Буфер обмена пуст или недоступен
            self.status.config(
                text="Буфер обмена пуст",
                fg=RED
            )
            
            self.root.after(
                1500,
                lambda: self.status.config(
                    text="Ожидание активации",
                    fg=MUTED
                )
            )

    def activate(self):

        key = self.entry.get().strip()

        if not key:

            self.status.config(
                text="Введите ключ.",
                fg=RED
            )

            return

        self.button.config(
            state="disabled",
            text="ПРОВЕРКА..."
        )

        self.status.config(
            text="Подключение к GitHub...",
            fg=MUTED
        )

        threading.Thread(
            target=self.worker,
            args=(key,),
            daemon=True
        ).start()

    def worker(self, key):

        success, message, info = check_license(
            key
        )

        self.root.after(
            0,
            self.finish,
            success,
            message,
            info
        )

    def finish(
        self,
        success,
        message,
        info
    ):

        if not success:

            self.status.config(
                text=message,
                fg=RED
            )

            self.button.config(
                state="normal",
                text="АКТИВИРОВАТЬ"
            )

            return

        self.root.destroy()

        MainWindow(
            info
        ).run()

    def run(self):

        self.root.mainloop()


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow:

    def __init__(
        self,
        license_info
    ):

        self.license_info = license_info

        self.discord_client = None

        self.stop_event = threading.Event()

        self.running = False
        
        self.license_window_open = False

        self.root = tk.Tk()

        self.root.title(
            "Katana Cloner"
        )

        self.root.geometry(
            "1050x650"
        )

        self.root.minsize(
            950,
            600
        )

        self.root.configure(
            bg=BG
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self.build()

    # ========================================================
    # UI
    # ========================================================

    def build(self):

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = tk.Frame(
            self.root,
            bg=BG
        )

        header.pack(
            fill="x",
            padx=28,
            pady=(22, 10)
        )

        title_frame = tk.Frame(
            header,
            bg=BG
        )

        title_frame.pack(
            side="left"
        )

        tk.Label(
            title_frame,
            text="KATANA",
            bg=BG,
            fg=TEXT,
            font=(
                "Segoe UI",
                23,
                "bold"
            )
        ).pack(
            side="left"
        )

        tk.Label(
            title_frame,
            text=" CLONER",
            bg=BG,
            fg=BLUE,
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        ).pack(
            side="left",
            pady=(8, 0)
        )

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
            font=(
                "Segoe UI",
                9,
                "bold"
            ),
            cursor="hand2"
        )

        self.license_button.pack(
            side="right",
            ipadx=14,
            ipady=7
        )

        # ----------------------------------------------------
        # Main content
        # ----------------------------------------------------

        content = tk.Frame(
            self.root,
            bg=BG
        )

        content.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=10
        )

        # Left
        left = tk.Frame(
            content,
            bg=BG
        )

        left.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 12)
        )

        # Right terminal
        right = tk.Frame(
            content,
            bg=PANEL
        )

        right.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(12, 0)
        )

        self.build_left(left)

        self.build_terminal(right)
        
        # ----------------------------------------------------
        # Footer с авторством
        # ----------------------------------------------------
        
        footer = tk.Frame(
            self.root,
            bg=BG
        )
        
        footer.pack(
            fill="x",
            padx=28,
            pady=(0, 10)
        )
        
        tk.Label(
            footer,
            text="Developer: katanov_soulchik  |  Script owner: sakuralol.121_50087",
            bg=BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                8
            ),
            justify="center"
        ).pack(
            side="bottom",
            pady=5
        )

    # ========================================================
    # LEFT PANEL
    # ========================================================

    def build_left(self, parent):

        card = tk.Frame(
            parent,
            bg=PANEL
        )

        card.pack(
            fill="both",
            expand=True
        )

        tk.Label(
            card,
            text="Настройки подключения",
            bg=PANEL,
            fg=TEXT,
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        ).pack(
            anchor="w",
            padx=25,
            pady=(25, 20)
        )

        self.create_label(
            card,
            "Токен аккаунта Discord"
        )

        self.token_entry = self.create_entry(
            card,
            show="●"
        )

        self.create_label(
            card,
            "ID исходного сервера"
        )

        self.source_entry = self.create_entry(
            card
        )

        self.create_label(
            card,
            "ID сервера назначения"
        )

        self.target_entry = self.create_entry(
            card
        )

        # Status
        status_frame = tk.Frame(
            card,
            bg=PANEL2
        )

        status_frame.pack(
            fill="x",
            padx=25,
            pady=(22, 10)
        )

        self.status_dot = tk.Label(
            status_frame,
            text="●",
            bg=PANEL2,
            fg=GREEN,
            font=(
                "Segoe UI",
                13
            )
        )
        
        self.status_dot.pack(
            side="left",
            padx=(12, 7)
        )

        self.status_text = tk.Label(
            status_frame,
            text="Готов к работе",
            bg=PANEL2,
            fg=GREEN,
            font=(
                "Segoe UI",
                9,
                "bold"
            )
        )

        self.status_text.pack(
            side="left",
            pady=10
        )

        # Buttons
        buttons = tk.Frame(
            card,
            bg=PANEL
        )

        buttons.pack(
            fill="x",
            padx=25,
            pady=20
        )

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
            font=(
                "Segoe UI",
                10,
                "bold"
            ),
            cursor="hand2"
        )

        self.start_button.pack(
            side="left",
            fill="x",
            expand=True,
            ipadx=10,
            ipady=11
        )

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
            font=(
                "Segoe UI",
                10,
                "bold"
            ),
            state="disabled",
            cursor="hand2"
        )

        self.stop_button.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(10, 0),
            ipadx=10,
            ipady=11
        )

        tk.Label(
            card,
            text=(
                "Используется токен аккаунта Discord.\n"
                "Аккаунт должен состоять на обоих серверах."
            ),
            bg=PANEL,
            fg=MUTED,
            font=(
                "Segoe UI",
                8
            ),
            wraplength=400,
            justify="left"
        ).pack(
            anchor="w",
            padx=25,
            pady=(5, 20)
        )

    # ========================================================
    # TERMINAL
    # ========================================================

    def build_terminal(self, parent):

        tk.Label(
            parent,
            text="Терминал",
            bg=PANEL,
            fg=TEXT,
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 10)
        )

        self.log_box = tk.Text(
            parent,
            bg="#080a0c",
            fg="#cfd5dc",
            insertbackground="#ffffff",
            selectbackground="#303741",
            relief="flat",
            bd=0,
            font=(
                "Consolas",
                9
            ),
            state="disabled",
            wrap="word"
        )

        self.log_box.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(0, 15)
        )

        self.log(
            "[SYSTEM] Katana Cloner запущен."
        )

        self.log(
            "[SYSTEM] Ожидание запуска."
        )

    # ========================================================
    # INPUT
    # ========================================================

    def create_label(
        self,
        parent,
        text
    ):

        tk.Label(
            parent,
            text=text,
            bg=PANEL,
            fg=MUTED,
            font=(
                "Segoe UI",
                9
            )
        ).pack(
            anchor="w",
            padx=25,
            pady=(7, 5)
        )

    def create_entry(
        self,
        parent,
        show=None
    ):

        entry = tk.Entry(
            parent,
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=(
                "Segoe UI",
                10
            ),
            show=show
        )

        entry.pack(
            fill="x",
            padx=25,
            ipady=10
        )

        return entry

    # ========================================================
    # LOG
    # ========================================================

    def log(self, text):

        def write():

            self.log_box.config(
                state="normal"
            )

            self.log_box.insert(
                "end",
                text + "\n"
            )

            self.log_box.see(
                "end"
            )

            self.log_box.config(
                state="disabled"
            )

        self.root.after(
            0,
            write
        )

    # ========================================================
    # LICENSE WINDOW
    # ========================================================

    def show_license(self):
        
        if self.license_window_open:
            return
        
        self.license_window_open = True

        info = tk.Toplevel(
            self.root
        )

        info.title(
            "Информация о лицензии"
        )

        info.geometry(
            "430x390"
        )

        info.resizable(
            False,
            False
        )

        info.configure(
            bg=BG
        )
        
        def on_close():
            self.license_window_open = False
            info.destroy()
        
        info.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(
            info,
            text="ЛИЦЕНЗИЯ",
            bg=BG,
            fg=TEXT,
            font=(
                "Segoe UI",
                20,
                "bold"
            )
        ).pack(
            pady=(30, 5)
        )

        tk.Label(
            info,
            text="Информация об активной лицензии",
            bg=BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                9
            )
        ).pack(
            pady=(0, 25)
        )

        data = [
            (
                "Статус",
                "АКТИВНА",
                GREEN
            ),
            (
                "Тип",
                self.license_info.get(
                    "type",
                    "UNKNOWN"
                ),
                CYAN
            ),
            (
                "Дата окончания",
                self.license_info.get(
                    "expires",
                    "—"
                ),
                YELLOW
            ),
            (
                "Использований",
                (
                    "∞"
                    if self.license_info.get(
                        "uses_left"
                    ) is None
                    else str(
                        self.license_info.get(
                            "uses_left"
                        )
                    )
                ),
                ORANGE
            ),
        ]

        for name, value, color in data:

            row = tk.Frame(
                info,
                bg=PANEL
            )

            row.pack(
                fill="x",
                padx=30,
                pady=4
            )

            tk.Label(
                row,
                text=name,
                bg=PANEL,
                fg=MUTED,
                font=(
                    "Segoe UI",
                    9
                )
            ).pack(
                side="left",
                padx=12,
                pady=10
            )

            tk.Label(
                row,
                text=value,
                bg=PANEL,
                fg=color,
                font=(
                    "Segoe UI",
                    9,
                    "bold"
                )
            ).pack(
                side="right",
                padx=12
            )

        hwid = self.license_info.get(
            "hwid",
            ""
        )

        tk.Label(
            info,
            text="HWID",
            bg=BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                8
            )
        ).pack(
            pady=(18, 2)
        )

        tk.Label(
            info,
            text=hwid,
            bg=BG,
            fg="#666f79",
            font=(
                "Consolas",
                7
            )
        ).pack(
            padx=20
        )

    # ========================================================
    # START
    # ========================================================

    def start_clone(self):

        if self.running:

            return

        token = self.token_entry.get().strip()

        source = self.source_entry.get().strip()

        target = self.target_entry.get().strip()

        if not token:

            messagebox.showerror(
                "Ошибка",
                "Введите токен аккаунта Discord."
            )

            return

        if not source.isdigit():

            messagebox.showerror(
                "Ошибка",
                "ID исходного сервера должен содержать только цифры."
            )

            return

        if not target.isdigit():

            messagebox.showerror(
                "Ошибка",
                "ID сервера назначения должен содержать только цифры."
            )

            return

        if source == target:

            messagebox.showerror(
                "Ошибка",
                "Серверы не должны совпадать."
            )

            return

        self.running = True

        self.stop_event.clear()

        self.start_button.config(
            state="disabled",
            text="РАБОТАЕТ..."
        )

        self.stop_button.config(
            state="normal",
            bg=RED,
            fg="white"
        )

        self.status_dot.config(
            fg=RED
        )
        
        self.status_text.config(
            text="Клонирование выполняется...",
            fg=RED
        )

        self.log(
            "[SYSTEM] Запуск Discord..."
        )

        threading.Thread(
            target=self.discord_worker,
            args=(
                token,
                int(source),
                int(target)
            ),
            daemon=True
        ).start()

    # ========================================================
    # DISCORD WORKER
    # ========================================================

    def discord_worker(
        self,
        token,
        source,
        target
    ):

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

    # ========================================================
    # STOP
    # ========================================================

    def stop_clone(self):

        if not self.running:

            return

        self.log(
            "[SYSTEM] Запрошена остановка..."
        )

        self.stop_event.set()

        self.stop_button.config(
            state="disabled",
            text="ОСТАНОВКА..."
        )

        self.status_text.config(
            text="Остановка...",
            fg=YELLOW
        )

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

    # ========================================================
    # FINISH
    # ========================================================

    def clone_finished(self):

        self.running = False

        self.start_button.config(
            state="normal",
            text="НАЧАТЬ"
        )

        self.stop_button.config(
            state="disabled",
            text="ОСТАНОВИТЬ",
            bg="#292f36",
            fg="#aaaaaa"
        )

        if self.stop_event.is_set():

            self.status_dot.config(
                fg=YELLOW
            )
            
            self.status_text.config(
                text="Остановлено",
                fg=YELLOW
            )

            self.log(
                "[SYSTEM] Операция остановлена."
            )

        else:

            self.status_dot.config(
                fg=GREEN
            )
            
            self.status_text.config(
                text="Готов к работе",
                fg=GREEN
            )
            
            self.log(
                "[SYSTEM] Клонирование завершено. Ожидание новых команд."
            )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        if self.running:

            answer = messagebox.askyesno(
                "Выход",
                "Клонирование ещё выполняется.\n"
                "Остановить операцию и выйти?"
            )

            if not answer:

                return

            self.stop_clone()

        self.root.after(
            300,
            self.root.destroy
        )

    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        self.root.mainloop()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        LicenseWindow().run()

    except Exception as e:

        print(
            f"Критическая ошибка: {e}"
        )

        input(
            "Нажмите Enter для выхода..."
        )