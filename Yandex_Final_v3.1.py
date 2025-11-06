import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import requests
import os
from urllib.parse import unquote, urlencode
from pathvalidate import sanitize_filename
import threading
import sys
import time
import re
import html
from bs4 import BeautifulSoup

# Попробуем импортировать tkinterdnd2 для Drag&Drop
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    print("Для Drag&Drop установите: pip install tkinterdnd2")

class ResponsiveUI:
    """Класс для управления масштабируемым интерфейсом"""
    
    def __init__(self, base_width=800, base_height=900):
        self.base_width = base_width
        self.base_height = base_height
        self.scale_factor = 1.0
        
        # Базовые размеры шрифтов и отступов
        self.base_font_sizes = {
            'title': 16,
            'heading': 11,
            'normal': 9,
            'small': 8,
            'button': 10
        }
        
        self.base_paddings = {
            'large': 20,
            'normal': 10,
            'small': 5,
            'tiny': 3
        }
    
    def calculate_scale(self, current_width, current_height):
        """Вычисляет коэффициент масштабирования по высоте только"""
        height_scale = current_height / self.base_height
        self.scale_factor = min(height_scale, 1.5)
        return self.scale_factor
    
    def get_font_size(self, size_type='normal'):
        """Получает масштабированный размер шрифта"""
        base_size = self.base_font_sizes.get(size_type, 9)
        return max(int(base_size * self.scale_factor), 7)
    
    def get_padding(self, padding_type='normal'):
        """Получает масштабированный отступ"""
        base_padding = self.base_paddings.get(padding_type, 10)
        return int(base_padding * self.scale_factor)
    
    def get_font(self, font_name='Arial', size_type='normal', weight='normal'):
        """Получает масштабированный шрифт"""
        font_size = self.get_font_size(size_type)
        return (font_name, font_size, weight)

class RoundedFrame(tk.Frame):
    """Кастомный фрейм с эффектом скругленных углов"""
    def __init__(self, parent, radius=15, bg='white', **kwargs):
        self.radius = radius
        self.bg = bg
        super().__init__(parent, bg=parent.cget('bg'), **kwargs)

        # Внутренний фрейм для создания эффекта скругления
        self.inner_frame = tk.Frame(self, bg=bg, relief='flat', bd=0)
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=radius//3, pady=radius//3)

class RoundedButton(tk.Frame):
    """Кастомная кнопка с скругленными углами"""
    def __init__(self, parent, text, command=None, radius=10, bg='#405c80', fg='white',
                 font=('Arial', 10, 'bold'), padx=20, pady=5, responsive_ui=None, **kwargs):
        super().__init__(parent, bg=parent.cget('bg'), relief='flat', bd=0)
        self.command = command
        self.bg = bg
        self.fg = fg
        self.responsive_ui = responsive_ui

        # Масштабированные параметры
        if responsive_ui:
            font = responsive_ui.get_font(font[0], 'button', font[2] if len(font) > 2 else 'normal')
            padx = responsive_ui.get_padding('normal')
            pady = responsive_ui.get_padding('small')

        # Создаем кнопку внутри фрейма
        self.button = tk.Button(self, text=text, command=self._on_click,
                                bg=bg, fg=fg, font=font, relief='flat',
                                bd=0, padx=padx, pady=pady, **kwargs)
        self.button.pack(fill=tk.BOTH, expand=True, padx=radius//2, pady=radius//2)

        # Привязываем события для hover эффекта
        self.button.bind('<Enter>', self._on_enter)
        self.button.bind('<Leave>', self._on_leave)

    def _on_click(self):
        if self.command:
            self.command()

    def _on_enter(self, event):
        darker = self._darken_color(self.bg, 20)
        self.button.configure(bg=darker)

    def _on_leave(self, event):
        self.button.configure(bg=self.bg)

    def _darken_color(self, color, amount):
        """Делает цвет темнее"""
        if color.startswith('#'):
            color = color[1:]
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darker = tuple(max(0, c - amount) for c in rgb)
        return f'#{darker[0]:02x}{darker[1]:02x}{darker[2]:02x}'

class YandexDiskDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("Yandex.Disk Mass Downloader v3.1")
        # ФИКСИРОВАННАЯ ШИРИНА 800px для избежания пустоты
        self.root.geometry("800x900")
        self.root.configure(bg='#f5f5f7')
        self.root.minsize(600, 600)  # Минимальный размер
        
        # Инициализируем адаптивный интерфейс
        self.responsive_ui = ResponsiveUI(base_width=800, base_height=900)

        # Цветовая схема
        self.bg_color = '#f5f5f7'
        self.card_bg = '#ffffff'
        self.header_bg = '#3a3a3a'
        self.text_color = '#333333'
        self.accent_color = '#5a7ea6'
        self.secondary_color = '#8e8e93'
        self.drop_highlight = '#e8f4f8'
        self.drop_border = '#d1d1d6'

        self.default_download_dir = self.get_default_download_dir()
        self.create_widgets()
        self.is_downloading = False
        self.cancel_requested = False
        
        self.downloaded_bytes = 0
        self.total_size_bytes = 0

        # Обработка изменения размера окна
        self.root.bind('<Configure>', self.on_window_resize)

        self.setup_drag_drop()

    def on_window_resize(self, event):
        """Обновляет масштабирование при изменении размера окна"""
        if event.widget == self.root:
            self.responsive_ui.calculate_scale(event.width, event.height)

    def get_default_download_dir(self):
        """Получает путь к папке загрузок рядом с исполняемым файлом"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        download_dir = os.path.join(base_dir, "Yandex_Downloads")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        return download_dir

    def create_widgets(self):
        # Главный контейнер с центрированием
        main_container = tk.Frame(self.root, bg=self.bg_color)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        header_frame = tk.Frame(main_container, bg=self.header_bg, height=90)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        # Внутренний фрейм заголовка с центрированием
        header_inner = tk.Frame(header_frame, bg=self.header_bg)
        header_inner.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 10))

        title_label = tk.Label(
            header_inner,
            text="Yandex.Disk Mass Downloader v3.1",
            bg=self.header_bg,
            fg='white',
            font=self.responsive_ui.get_font('Arial', 'title', 'bold'),
            pady=self.responsive_ui.get_padding('large')
        )
        title_label.pack(fill=tk.X, expand=True)

        # Основное содержимое - растягивается на всю ширину
        content_wrapper = tk.Frame(main_container, bg=self.bg_color)
        content_wrapper.pack(fill=tk.BOTH, expand=True, padx=self.responsive_ui.get_padding('normal'),
                           pady=self.responsive_ui.get_padding('normal'))

        # Canvas для скролирования
        main_canvas = tk.Canvas(content_wrapper, bg=self.bg_color, highlightthickness=0)
        main_canvas.pack(fill=tk.BOTH, expand=True)

        # Основной фрейм контента
        main_frame = tk.Frame(main_canvas, bg=self.bg_color)
        canvas_window = main_canvas.create_window((0, 0), window=main_frame, anchor=tk.NW)

        def on_configure(event):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))
            # Растягиваем окно по ширине canvas
            main_canvas.itemconfig(canvas_window, width=main_canvas.winfo_width())

        main_frame.bind("<Configure>", on_configure)
        main_canvas.bind("<Configure>", lambda e: main_canvas.itemconfig(canvas_window, width=e.width))

        # Карточка для ввода ссылок
        links_card = self.create_rounded_card(main_frame, "Ссылки для загрузки")
        links_card.pack(fill=tk.BOTH, expand=False, pady=(0, self.responsive_ui.get_padding('normal')))

        # Кнопки управления
        btn_frame = tk.Frame(links_card.inner_frame, bg=self.card_bg)
        btn_frame.pack(fill=tk.X, pady=(0, self.responsive_ui.get_padding('normal')))

        # Контейнер для центрирования кнопок
        btn_center = tk.Frame(btn_frame, bg=self.card_bg)
        btn_center.pack(expand=True)

        RoundedButton(btn_center, text="Вставить текст",
                     command=self.paste_text_from_clipboard,
                     bg=self.secondary_color, fg='white',
                     responsive_ui=self.responsive_ui).pack(side=tk.LEFT, 
                     padx=self.responsive_ui.get_padding('small'))

        RoundedButton(btn_center, text="Вставить ссылки",
                     command=self.paste_links_from_clipboard,
                     bg=self.secondary_color, fg='white',
                     responsive_ui=self.responsive_ui).pack(side=tk.LEFT, 
                     padx=self.responsive_ui.get_padding('small'))

        RoundedButton(btn_center, text="Загрузить HTML",
                     command=self.load_html_file,
                     bg=self.secondary_color, fg='white',
                     responsive_ui=self.responsive_ui).pack(side=tk.LEFT, 
                     padx=self.responsive_ui.get_padding('small'))

        RoundedButton(btn_center, text="Очистить поле",
                     command=self.clear_links,
                     bg='#8e8e93', fg='white',
                     responsive_ui=self.responsive_ui).pack(side=tk.LEFT,
                     padx=self.responsive_ui.get_padding('small'))

        # Область для Drag&Drop
        drop_container = tk.Frame(links_card.inner_frame, bg=self.card_bg)
        drop_container.pack(fill=tk.BOTH, expand=True, pady=self.responsive_ui.get_padding('small'))

        self.drop_area = tk.Frame(drop_container, bg=self.drop_border, relief='flat', bd=1)
        self.drop_area.pack(fill=tk.BOTH, expand=True)

        self.drop_content = tk.Frame(self.drop_area, bg='white')
        self.drop_content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Поле для ввода ссылок
        self.links_text = scrolledtext.ScrolledText(
            self.drop_content,
            width=80,
            height=8,
            bg='white',
            fg=self.text_color,
            font=self.responsive_ui.get_font('Arial', 'normal'),
            relief='flat',
            borderwidth=0
        )
        self.links_text.pack(fill=tk.BOTH, expand=True)

        # ВОССТАНОВЛЕННАЯ подсказка для Drag&Drop - ОВЕРЛЕЙНАЯ
        self.drop_label = tk.Label(
            self.drop_content,
            text="ПЕРЕТАЩИТЕ HTML ФАЙЛЫ СЮДА\n(или вставьте ссылки вручную)\n\n📁 Перетащите файл в эту область",
            bg='white',
            fg='#999999',
            font=self.responsive_ui.get_font('Arial', 'normal', 'bold'),
            justify=tk.CENTER
        )
        # Изначально показываем подсказку
        self.drop_label.place(in_=self.drop_content, relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Привязываем события к текстовому полю для скрытия подсказки
        self.links_text.bind('<FocusIn>', lambda e: self.hide_drop_hint())
        self.links_text.bind('<Key>', lambda e: self.hide_drop_hint())

        # Карточка настроек
        settings_card = self.create_rounded_card(main_frame, "Настройки загрузки")
        settings_card.pack(fill=tk.X, pady=(0, self.responsive_ui.get_padding('normal')))

        # Выбор папки
        folder_frame = tk.Frame(settings_card.inner_frame, bg=self.card_bg)
        folder_frame.pack(fill=tk.X, pady=self.responsive_ui.get_padding('normal'))

        tk.Label(folder_frame, text="Папка для сохранения:",
                bg=self.card_bg, fg=self.text_color,
                font=self.responsive_ui.get_font('Arial', 'normal')).pack(anchor=tk.W)

        path_frame = tk.Frame(folder_frame, bg=self.card_bg)
        path_frame.pack(fill=tk.X, pady=self.responsive_ui.get_padding('small'))

        self.folder_path = tk.StringVar(value=self.default_download_dir)

        entry_frame = tk.Frame(path_frame, bg=self.bg_color)
        entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        entry_inner = tk.Frame(entry_frame, bg='white', relief='flat', bd=1)
        entry_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        folder_entry = tk.Entry(entry_inner, textvariable=self.folder_path,
                               bg='white', fg=self.text_color,
                               font=self.responsive_ui.get_font('Arial', 'normal'),
                               relief='flat', borderwidth=0)
        folder_entry.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        RoundedButton(path_frame, text="Обзор",
                     command=self.browse_folder,
                     bg=self.secondary_color, fg='white',
                     responsive_ui=self.responsive_ui).pack(side=tk.LEFT,
                     padx=(self.responsive_ui.get_padding('small'), 0))

        # Переключатель для перезаписи
        self.overwrite_var = tk.BooleanVar(value=False)
        overwrite_check = tk.Checkbutton(settings_card.inner_frame,
                                        text="Перезаписать существующие файлы",
                                        variable=self.overwrite_var,
                                        bg=self.card_bg, fg=self.text_color,
                                        font=self.responsive_ui.get_font('Arial', 'normal'),
                                        selectcolor=self.card_bg)
        overwrite_check.pack(anchor=tk.W, padx=self.responsive_ui.get_padding('normal'),
                           pady=(0, self.responsive_ui.get_padding('normal')))

        # Карточка прогресса
        progress_card = self.create_rounded_card(main_frame, "Прогресс загрузки")
        progress_card.pack(fill=tk.X, pady=(0, self.responsive_ui.get_padding('normal')))

        # Информация о статусе
        self.stats_label = tk.Label(progress_card.inner_frame, text="Готов к работе",
                                   bg=self.card_bg, fg=self.text_color,
                                   font=self.responsive_ui.get_font('Arial', 'normal', 'bold'))
        self.stats_label.pack(fill=tk.X, pady=(0, self.responsive_ui.get_padding('normal')))

        # Прогрессбар с информацией
        progress_frame = tk.Frame(progress_card.inner_frame, bg=self.card_bg)
        progress_frame.pack(fill=tk.X, pady=(0, self.responsive_ui.get_padding('small')))

        self.progress = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        self.progress.pack(fill=tk.X, side=tk.LEFT, expand=True,
                          padx=(0, self.responsive_ui.get_padding('normal')))

        self.mb_label = tk.Label(progress_frame, text="0 МБ / 0 МБ",
                                bg=self.card_bg, fg=self.text_color,
                                font=self.responsive_ui.get_font('Arial', 'normal', 'bold'),
                                width=15)
        self.mb_label.pack(side=tk.LEFT)

        # Процент загрузки
        self.percent_label = tk.Label(progress_card.inner_frame, text="0%",
                                     bg=self.card_bg, fg=self.text_color,
                                     font=self.responsive_ui.get_font('Arial', 'normal'))
        self.percent_label.pack(fill=tk.X)

        # Кнопки управления загрузкой
        btn_control_frame = tk.Frame(progress_card.inner_frame, bg=self.card_bg)
        btn_control_frame.pack(fill=tk.X, pady=(self.responsive_ui.get_padding('normal'), 0))

        # Центрирующий контейнер для кнопок
        btn_center_control = tk.Frame(btn_control_frame, bg=self.card_bg)
        btn_center_control.pack(expand=True)

        self.download_btn = RoundedButton(btn_center_control, text="Начать загрузку",
                                         command=self.start_download,
                                         bg=self.accent_color, fg='white',
                                         responsive_ui=self.responsive_ui)
        self.download_btn.pack(side=tk.LEFT, padx=self.responsive_ui.get_padding('small'))

        self.cancel_btn = RoundedButton(btn_center_control, text="Отменить",
                                       command=self.cancel_download,
                                       bg='#d32f2f', fg='white',
                                       responsive_ui=self.responsive_ui)
        self.cancel_btn.pack(side=tk.LEFT, padx=self.responsive_ui.get_padding('small'))
        self.cancel_btn.button.config(state='disabled')

        RoundedButton(btn_center_control, text="Очистить всё",
                     command=self.clear_all,
                     bg='#8e8e93', fg='white',
                     responsive_ui=self.responsive_ui).pack(side=tk.LEFT,
                     padx=self.responsive_ui.get_padding('small'))

        # Карточка логов
        logs_card = self.create_rounded_card(main_frame, "Логи загрузки")
        logs_card.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        self.log_text = scrolledtext.ScrolledText(
            logs_card.inner_frame,
            width=80,
            height=10,
            bg='#1e1e1e',
            fg='#00ff00',
            font=self.responsive_ui.get_font('Courier New', 'small'),
            relief='flat',
            borderwidth=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def create_rounded_card(self, parent, title):
        """Создает карточку с заголовком"""
        card_frame = RoundedFrame(parent, radius=12, bg=self.card_bg)

        # Заголовок карточки
        title_label = tk.Label(card_frame.inner_frame, text=title,
                              bg=self.card_bg, fg=self.text_color,
                              font=self.responsive_ui.get_font('Arial', 'heading', 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, self.responsive_ui.get_padding('small')))

        # Разделитель
        separator = tk.Frame(card_frame.inner_frame, bg='#e0e0e0', height=1)
        separator.pack(fill=tk.X, pady=(0, self.responsive_ui.get_padding('normal')))

        return card_frame

    def setup_drag_drop(self):
        """Настраивает Drag&Drop если доступно"""
        if not DND_AVAILABLE:
            return

        try:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind('<<Drop>>', self.drop_handler)
            self.drop_area.dnd_bind('<<DragEnter>>', self.drag_enter)
            self.drop_area.dnd_bind('<<DragLeave>>', self.drag_leave)
        except:
            pass

    def drag_enter(self, event):
        """Визуальный эффект при переносе файла"""
        self.drop_area.config(bg=self.drop_highlight)

    def drag_leave(self, event):
        """Возвращение нормального вида"""
        self.drop_area.config(bg=self.drop_border)

    def drop_handler(self, event):
        """Обработка перетащенных файлов"""
        self.drag_leave(None)
        files = self.parse_dnd_files(event.data)
        for file_path in files:
            if file_path.lower().endswith(('.html', '.htm', '.txt')):
                self.process_html_file(file_path)

    def parse_dnd_files(self, data):
        """Парсит пути файлов из Drag&Drop"""
        if not data:
            return []

        files = []
        if data.startswith('{'):
            import re
            matches = re.findall(r'[^{}]+', data)
            files = [f.strip() for f in matches if f.strip()]
        else:
            files = data.split()

        return files

    def show_drop_hint(self):
        """Показывает подсказку Drag&Drop"""
        self.drop_label.place(in_=self.drop_content, relx=0.5, rely=0.5, anchor=tk.CENTER)

    def hide_drop_hint(self):
        """Скрывает подсказку Drag&Drop"""
        self.drop_label.place_forget()

    def paste_text_from_clipboard(self):
        """Вставляет текст из буфера обмена"""
        try:
            clipboard_text = self.root.clipboard_get()
            if clipboard_text:
                self.links_text.delete(1.0, tk.END)
                self.links_text.insert(1.0, clipboard_text)
                self.hide_drop_hint()
                self.log("Текст из буфера обмена успешно вставлен")
        except Exception as e:
            self.log(f"Ошибка при вставке из буфера обмена: {str(e)}")

    def paste_links_from_clipboard(self):
        """Извлекает ссылки из буфера обмена"""
        try:
            clipboard_text = self.root.clipboard_get()
            if not clipboard_text:
                self.log("Буфер обмена пуст")
                return

            extracted_links = self.extract_urls_from_text(clipboard_text)

            if extracted_links:
                self.links_text.delete(1.0, tk.END)
                self.links_text.insert(1.0, '\n'.join(extracted_links))
                self.hide_drop_hint()
                self.log(f"Извлечено и вставлено {len(extracted_links)} ссылок")
            else:
                self.log("Ссылки Яндекс.Диска не найдены в буфере обмена")
        except Exception as e:
            self.log(f"Ошибка при извлечении ссылок: {str(e)}")

    def load_html_file(self):
        """Загружает HTML файл и извлекает ссылки"""
        try:
            file_path = filedialog.askopenfilename(
                title="Выберите HTML файл",
                filetypes=[("HTML files", "*.html;*.htm"), ("Text files", "*.txt"), ("All files", "*.*")]
            )

            if file_path:
                self.process_html_file(file_path)
        except Exception as e:
            self.log(f"Ошибка при загрузке HTML файла: {str(e)}")

    def process_html_file(self, file_path):
        """Обрабатывает HTML файл"""
        try:
            self.log(f"Обработка HTML файла: {os.path.basename(file_path)}")
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            extracted_links = self.extract_urls_from_text(html_content)

            if extracted_links:
                current_content = self.links_text.get(1.0, tk.END).strip()
                new_content = current_content + '\n' + '\n'.join(extracted_links) if current_content else '\n'.join(extracted_links)
                self.links_text.delete(1.0, tk.END)
                self.links_text.insert(1.0, new_content)
                self.hide_drop_hint()
                self.log(f"Из HTML файла извлечено {len(extracted_links)} ссылок Яндекс.Диска")
            else:
                self.log("В HTML файле не найдено ссылок Яндекс.Диска")
        except Exception as e:
            self.log(f"Ошибка при обработке HTML файла: {str(e)}")

    def extract_urls_from_text(self, text):
        """Извлекает URL из текста"""
        urls = []
        if not text:
            return urls

        text = html.unescape(text)

        patterns = [
            r'<a[^>]*href\s*=\s*["\'](https?://[^"\']*yandex[^"\']*|https?://[^"\']*yadi\.sk[^"\']*)["\'][^>]*>',
            r'\[[^\]]*\]\((https?://[^)]*yandex[^)]*|https?://[^)]*yadi\.sk[^)]*)\)',
            r'(https?://[^\s<>"\'\(\)]*yandex[^\s<>"\'\(\)]*|https?://[^\s<>"\'\(\)]*yadi\.sk[^\s<>"\'\(\)]*)'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(matches)

        valid_urls = []
        for url in set(urls):
            if any(domain in url for domain in ['yandex.ru', 'yandex.com', 'yadi.sk', 'disk.yandex']):
                clean_url = self.clean_url(url)
                if clean_url:
                    valid_urls.append(clean_url)

        return valid_urls

    def clean_url(self, url):
        """Очищает URL"""
        try:
            url = url.rstrip('.,;:!?')
            if url.endswith(')') and url.count('(') < url.count(')'):
                url = url[:-1]
            if url.endswith('"') or url.endswith("'"):
                url = url[:-1]
            return url
        except:
            return None

    def clear_links(self):
        """Очищает поле ссылок"""
        self.links_text.delete(1.0, tk.END)
        self.show_drop_hint()

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)

    def clear_all(self):
        """Очищает всё"""
        self.links_text.delete(1.0, tk.END)
        self.log_text.delete(1.0, tk.END)
        self.progress['value'] = 0
        self.mb_label.config(text="0 МБ / 0 МБ")
        self.percent_label.config(text="0%")
        self.stats_label.config(text="Готов к работе")
        self.downloaded_bytes = 0
        self.total_size_bytes = 0
        self.show_drop_hint()

    def log(self, message):
        """Логирует сообщение"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def start_download(self):
        """Начинает загрузку"""
        if self.is_downloading:
            return

        links_text = self.links_text.get(1.0, tk.END).strip()
        links = self.extract_urls_from_text(links_text)
        save_path = self.folder_path.get()

        if not links:
            messagebox.showerror("Ошибка", "Не найдено валидных ссылок Яндекс.Диска")
            return

        if not save_path:
            messagebox.showerror("Ошибка", "Выберите папку для сохранения")
            return

        if not os.path.exists(save_path):
            os.makedirs(save_path)

        self.is_downloading = True
        self.cancel_requested = False
        self.downloaded_bytes = 0
        self.total_size_bytes = 0
        
        self.download_btn.button.config(state='disabled')
        self.cancel_btn.button.config(state='normal')

        thread = threading.Thread(target=self.download_files, args=(links, save_path))
        thread.daemon = True
        thread.start()

    def cancel_download(self):
        """Отменяет загрузку"""
        self.cancel_requested = True
        self.log("⚠️ Загрузка отменена пользователем...")

    def download_files(self, links, save_path):
        """Загружает файлы"""
        total_files = len(links)
        successful = 0
        failed = 0
        cancelled = 0

        self.progress['maximum'] = total_files
        self.progress['value'] = 0
        self.log(f"Начало загрузки {total_files} файлов...")
        self.log(f"Папка сохранения: {save_path}")

        for i, link in enumerate(links):
            if self.cancel_requested:
                cancelled += 1
                self.log(f"[{i+1}/{total_files}] ⏭️ Пропущено (отмена)")
                continue

            try:
                self.stats_label.config(text=f"Обработка {i+1}/{total_files} | Скачано: {self.format_bytes(self.downloaded_bytes)}")
                self.log(f"[{i+1}/{total_files}] Обработка: {link}")

                if self.download_file_correct(link, save_path):
                    successful += 1
                else:
                    failed += 1

                self.progress['value'] = i + 1
                percent = int((i + 1) / total_files * 100)
                self.percent_label.config(text=f"{percent}%")

                time.sleep(0.5)
            except Exception as e:
                failed += 1
                self.log(f"✗ Ошибка: {str(e)}")

        self.is_downloading = False
        self.download_btn.button.config(state='normal')
        self.cancel_btn.button.config(state='disabled')

        summary = f"Завершено! Успешно: {successful}, Ошибок: {failed}"
        if cancelled > 0:
            summary += f", Отменено: {cancelled}"

        self.stats_label.config(text=summary)
        self.log(f"=== {summary} ===")

        if successful > 0:
            messagebox.showinfo("Готово", f"Загрузка завершена!\nУспешно: {successful}\nОшибок: {failed}\nОтменено: {cancelled}")

    def download_file_correct(self, public_key, save_path):
        """Скачивает файл"""
        try:
            base_url = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?'
            final_url = base_url + urlencode(dict(public_key=public_key))

            response = requests.get(final_url, timeout=30)

            if response.status_code != 200:
                self.log(f"Ошибка получения ссылки: {response.status_code}")
                return False

            download_url = response.json()['href']
            filename = self.get_filename_from_url(download_url) or f"file_{int(time.time())}.downloaded"
            safe_filename = sanitize_filename(filename)
            full_path = os.path.join(save_path, safe_filename)

            if os.path.exists(full_path) and not self.overwrite_var.get():
                self.log(f"⚠️ Файл уже существует: {safe_filename}")
                return False

            file_size = 0
            chunk_size = 1024 * 1024

            response = requests.get(download_url, stream=True, timeout=30)

            if response.status_code != 200:
                self.log(f"Ошибка загрузки: {response.status_code}")
                return False

            try:
                file_size = int(response.headers.get('content-length', 0))
            except:
                pass

            self.total_size_bytes = file_size

            with open(full_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self.cancel_requested:
                        f.close()
                        if os.path.exists(full_path):
                            os.remove(full_path)
                        return False

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.downloaded_bytes += len(chunk)

                        mb_downloaded = self.downloaded_bytes / (1024 * 1024)
                        mb_total = self.total_size_bytes / (1024 * 1024)
                        self.mb_label.config(text=f"{mb_downloaded:.1f} МБ / {mb_total:.1f} МБ")

            self.log(f"✓ Скачано: {safe_filename} ({self.format_bytes(file_size)})")
            return True

        except Exception as e:
            self.log(f"✗ Ошибка при скачивании: {str(e)}")
            return False

    def get_filename_from_url(self, url):
        """Получает имя файла из URL"""
        try:
            filename_part = url.split('filename=')[1]
            filename = unquote(filename_part.split('&')[0], encoding='utf-8')
            return filename if filename and '.' in filename else None
        except:
            return None

    def format_bytes(self, bytes_size):
        """Форматирует размер в человеко-читаемый вид"""
        for unit in ['B', 'КБ', 'МБ', 'ГБ']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} ТБ"

def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    app = YandexDiskDownloader(root)
    root.mainloop()

if __name__ == "__main__":
    main()
