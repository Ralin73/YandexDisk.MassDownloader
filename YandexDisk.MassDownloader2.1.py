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
                 font=('Arial', 10, 'bold'), padx=20, pady=5, **kwargs):
        super().__init__(parent, bg=parent.cget('bg'), relief='flat', bd=0)
        
        self.command = command
        self.bg = bg
        self.fg = fg
        
        # Создаем кнопку внутри фрейма с отступами для эффекта скругления
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
        # Эффект при наведении - немного темнее
        darker = self._darken_color(self.bg, 20)
        self.button.configure(bg=darker)
        
    def _on_leave(self, event):
        # Возвращаем исходный цвет
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
        self.root.title("Yandex.Disk Mass Downloader v2.0")
        self.root.geometry("900x750")
        self.root.configure(bg='#f5f5f7')
        
        # Цветовая схема в мягких серых тонах
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
        
        # Настройка Drag&Drop
        self.setup_drag_drop()
        
        # Настройка горячих клавиш
        self.setup_hotkeys()
        
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
        # Заголовок с скругленными нижними углами
        header_frame = tk.Frame(self.root, bg=self.header_bg, height=90)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Внутренний фрейм для эффекта скругления
        header_inner = tk.Frame(header_frame, bg=self.header_bg)
        header_inner.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 10))
        
        title_label = tk.Label(header_inner, 
                              text="Yandex.Disk Mass Downloader", 
                              bg=self.header_bg, 
                              fg='white',
                              font=('Arial', 16, 'bold'),
                              pady=20)
        title_label.pack(fill=tk.X)
        
        # Основной контент
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Карточка для ввода ссылок с областью Drag&Drop
        links_card = self.create_rounded_card(main_frame, "Ссылки для загрузки")
        links_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Кнопки управления с скругленными углами
        btn_frame = tk.Frame(links_card.inner_frame, bg=self.card_bg)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Создаем скругленные кнопки
        RoundedButton(btn_frame, text="Вставить текст", 
                     command=self.paste_text_from_clipboard,
                     bg=self.secondary_color, fg='white',
                     font=('Arial', 9), radius=8).pack(side=tk.LEFT, padx=(0,5))
        
        RoundedButton(btn_frame, text="Вставить ссылки", 
                     command=self.paste_links_from_clipboard,
                     bg=self.secondary_color, fg='white',
                     font=('Arial', 9), radius=8).pack(side=tk.LEFT, padx=(0,5))
        
        RoundedButton(btn_frame, text="Загрузить HTML", 
                     command=self.load_html_file,
                     bg=self.secondary_color, fg='white',
                     font=('Arial', 9), radius=8).pack(side=tk.LEFT, padx=(0,5))
        
        RoundedButton(btn_frame, text="Очистить поле", 
                     command=self.clear_links,
                     bg='#8e8e93', fg='white',
                     font=('Arial', 9), radius=8).pack(side=tk.LEFT)
        
        # Область для Drag&Drop с скругленными углами
        drop_container = tk.Frame(links_card.inner_frame, bg=self.card_bg)
        drop_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.drop_area = tk.Frame(drop_container, bg=self.drop_border, relief='flat', bd=1)
        self.drop_area.pack(fill=tk.BOTH, expand=True)
        
        # Внутренний фрейм для содержимого
        self.drop_content = tk.Frame(self.drop_area, bg='white')
        self.drop_content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Поле для ввода ссылок
        self.links_text = scrolledtext.ScrolledText(
            self.drop_content, 
            width=80, 
            height=12,
            bg='white',
            fg=self.text_color,
            font=('Arial', 9),
            relief='flat',
            borderwidth=0
        )
        self.links_text.pack(fill=tk.BOTH, expand=True)
        
        # Подсказка для Drag&Drop - СДЕЛАЕМ ПРОЗРАЧНОЙ ДЛЯ СОБЫТИЙ
        self.drop_label = tk.Label(
            self.drop_content,
            text="ПЕРЕТАЩИТЕ HTML ФАЙЛЫ СЮДА\n(или вставьте ссылки вручную)\n\n📁 Перетащите файл в эту область",
            bg='white',
            fg='#666666',
            font=('Arial', 10, 'bold'),
            justify=tk.CENTER
        )
        
        # Карточка настроек с скругленными углами
        settings_card = self.create_rounded_card(main_frame, "Настройки загрузки")
        settings_card.pack(fill=tk.X, pady=(0, 15))
        
        # Выбор папки
        folder_frame = tk.Frame(settings_card.inner_frame, bg=self.card_bg)
        folder_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(folder_frame, text="Папка для сохранения:", 
                bg=self.card_bg, fg=self.text_color,
                font=('Arial', 9)).pack(anchor=tk.W)
        
        path_frame = tk.Frame(folder_frame, bg=self.card_bg)
        path_frame.pack(fill=tk.X, pady=5)
        
        self.folder_path = tk.StringVar(value=self.default_download_dir)
        
        # Поле ввода с скругленными углами
        entry_frame = tk.Frame(path_frame, bg=self.bg_color)
        entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        entry_inner = tk.Frame(entry_frame, bg='white', relief='flat', bd=1)
        entry_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        folder_entry = tk.Entry(entry_inner, textvariable=self.folder_path, 
                               bg='white', fg=self.text_color,
                               font=('Arial', 9), relief='flat', borderwidth=0)
        folder_entry.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        
        # Кнопка обзора с скругленными углами
        RoundedButton(path_frame, text="Обзор", command=self.browse_folder,
                     bg=self.secondary_color, fg='white',
                     font=('Arial', 9), radius=6, padx=12, pady=4).pack(side=tk.RIGHT, padx=(5,0))
        
        # Статистика и прогресс
        self.stats_label = tk.Label(settings_card.inner_frame, text="Готов к работе", 
                                   bg=self.card_bg, fg=self.text_color,
                                   font=('Arial', 9))
        self.stats_label.pack(anchor=tk.W, pady=5)
        
        # Прогресс-бар в скругленном контейнере
        progress_frame = tk.Frame(settings_card.inner_frame, bg=self.card_bg)
        progress_frame.pack(fill=tk.X, pady=10)
        
        progress_container = tk.Frame(progress_frame, bg=self.bg_color)
        progress_container.pack(fill=tk.X)
        
        progress_inner = tk.Frame(progress_container, bg='#e5e5ea', relief='flat', bd=0)
        progress_inner.pack(fill=tk.X, padx=1, pady=1)
        
        self.progress = ttk.Progressbar(progress_inner, length=400, mode='determinate')
        self.progress.pack(fill=tk.X, padx=2, pady=2)
        
        # Кнопки управления загрузкой
        control_frame = tk.Frame(settings_card.inner_frame, bg=self.card_bg)
        control_frame.pack(fill=tk.X, pady=10)
        
        self.download_btn = RoundedButton(control_frame, text="Начать загрузку", 
                                         command=self.start_download,
                                         bg=self.accent_color, fg='white', 
                                         font=('Arial', 10, 'bold'),
                                         radius=10, padx=20, pady=8)
        self.download_btn.pack(side=tk.LEFT, padx=(0,10))
        
        RoundedButton(control_frame, text="Очистить всё", command=self.clear_all,
                     bg='#8e8e93', fg='white',
                     font=('Arial', 9), radius=8).pack(side=tk.LEFT)
        
        # Карточка лога с скругленными углами
        log_card = self.create_rounded_card(main_frame, "Лог выполнения")
        log_card.pack(fill=tk.BOTH, expand=True)
        
        # Лог в скругленном контейнере
        log_container = tk.Frame(log_card.inner_frame, bg=self.card_bg)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        log_border = tk.Frame(log_container, bg='#d1d1d6', relief='flat', bd=1)
        log_border.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        log_inner = tk.Frame(log_border, bg='#f8f8f8')
        log_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_inner, 
            width=80, 
            height=12,
            bg='#f8f8f8',
            fg=self.text_color,
            font=('Consolas', 8),
            relief='flat',
            borderwidth=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Показываем подсказку о Drag&Drop при запуске
        self.show_drop_hint()
        
        # Создаем контекстное меню
        self.create_context_menus()
        
        # Отслеживаем ввод текста для автоматического скрытия подсказки
        self.setup_text_monitoring()
        
    def setup_text_monitoring(self):
        """Настройка отслеживания ввода текста для автоматического скрытия подсказки"""
        # Переменная для отслеживания предыдущего состояния
        self.previous_text = ""
        
        # Функция для проверки изменений
        def check_text_change():
            current_text = self.links_text.get(1.0, tk.END).strip()
            
            # Если текст изменился и стал непустым, скрываем подсказку
            if current_text != self.previous_text:
                self.previous_text = current_text
                if current_text:
                    self.hide_drop_hint()
                else:
                    self.show_drop_hint()
            
            # Повторяем проверку через 100 мс
            self.root.after(100, check_text_change)
        
        # Запускаем мониторинг
        check_text_change()
        
    def create_rounded_card(self, parent, title):
        """Создает карточку с эффектом скругленных углов"""
        card = RoundedFrame(parent, radius=12, bg=self.card_bg)
        
        # Заголовок карточки
        title_label = tk.Label(card.inner_frame, text=title, bg=self.card_bg, fg=self.text_color, 
                              font=('Arial', 11, 'bold'), anchor=tk.W)
        title_label.pack(fill=tk.X, pady=(0,10))
        
        return card
        
    def setup_drag_drop(self):
        """Настройка Drag&Drop функциональности"""
        if DND_AVAILABLE:
            try:
                # Регистрируем область как цель для перетаскивания
                self.links_text.drop_target_register(DND_FILES)
                self.links_text.dnd_bind('<<Drop>>', self.on_drop)
                
                # ДОПОЛНИТЕЛЬНО: делаем метку прозрачной для событий Drag&Drop
                self.drop_label.drop_target_register(DND_FILES)
                self.drop_label.dnd_bind('<<Drop>>', self.on_drop)
                
                self.log("Drag&Drop активирован - перетащите HTML файлы в текстовую область")
            except Exception as e:
                self.log(f"Ошибка настройки Drag&Drop: {str(e)}")
        else:
            self.log("Drag&Drop недоступен. Установите: pip install tkinterdnd2")
            
    def setup_hotkeys(self):
        """Настройка горячих клавиш, работающих с любыми раскладками"""
        # Универсальные горячие клавиши (работают с любой раскладкой)
        self.root.bind_all('<Control-KeyPress>', self.handle_ctrl_hotkey)
        self.root.bind_all('<Control-Key>', self.handle_ctrl_hotkey)
        
    def handle_ctrl_hotkey(self, event):
        """Обработчик Ctrl+клавиша, работающий с любыми раскладками"""
        # Получаем код клавиши
        keycode = event.keycode
        keysym = event.keysym.lower()
        
        # Определяем какая клавиша нажата с Ctrl
        # Коды клавиш для C, V, X, A (работают независимо от раскладки)
        if event.state & 0x4:  # Проверяем что Ctrl нажат
            focused_widget = self.root.focus_get()
            
            # Ctrl+C - Копирование
            if keycode == 54 or keysym in ['c', 'с']:  # Английская 'c' и русская 'с'
                if focused_widget == self.links_text:
                    self.copy_text()
                elif focused_widget == self.log_text:
                    self.copy_log_text()
                return "break"
            
            # Ctrl+V - Вставка
            elif keycode == 55 or keysym in ['v', 'м']:  # Английская 'v' и русская 'м'
                if focused_widget == self.links_text:
                    self.paste_text()
                return "break"
            
            # Ctrl+X - Вырезание
            elif keycode == 53 or keysym in ['x', 'ч']:  # Английская 'x' и русская 'ч'
                if focused_widget == self.links_text:
                    self.cut_text()
                return "break"
            
            # Ctrl+A - Выделение всего
            elif keycode == 38 or keysym in ['a', 'ф']:  # Английская 'a' и русская 'ф'
                if focused_widget == self.links_text:
                    self.select_all()
                elif focused_widget == self.log_text:
                    self.select_all_log()
                return "break"
        
    def create_context_menus(self):
        """Создает контекстные меню для текстовых полей"""
        # Контекстное меню для поля ссылок
        self.context_menu_links = tk.Menu(self.root, tearoff=0, bg='white', fg=self.text_color, font=('Arial', 9))
        self.context_menu_links.add_command(label="Вырезать (Ctrl+X)", command=self.cut_text)
        self.context_menu_links.add_command(label="Копировать (Ctrl+C)", command=self.copy_text)
        self.context_menu_links.add_command(label="Вставить (Ctrl+V)", command=self.paste_text)
        self.context_menu_links.add_separator()
        self.context_menu_links.add_command(label="Выделить всё (Ctrl+A)", command=self.select_all)
        
        # Контекстное меню для лога
        self.context_menu_log = tk.Menu(self.root, tearoff=0, bg='white', fg=self.text_color, font=('Arial', 9))
        self.context_menu_log.add_command(label="Копировать (Ctrl+C)", command=self.copy_log_text)
        self.context_menu_log.add_separator()
        self.context_menu_log.add_command(label="Выделить всё (Ctrl+A)", command=self.select_all_log)
        self.context_menu_log.add_command(label="Очистить лог", command=self.clear_log)
        
        # Привязываем контекстные меню к виджетам
        self.links_text.bind("<Button-3>", self.show_context_menu_links)
        self.log_text.bind("<Button-3>", self.show_context_menu_log)
        
    def show_context_menu_links(self, event):
        """Показывает контекстное меню для поля ссылок"""
        try:
            self.context_menu_links.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu_links.grab_release()
            
    def show_context_menu_log(self, event):
        """Показывает контекстное меню для поля лога"""
        try:
            self.context_menu_log.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu_log.grab_release()
        
    def show_drop_hint(self):
        """Показывает подсказку о Drag&Drop"""
        if not self.links_text.get(1.0, tk.END).strip():
            self.drop_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            # ДЕЛАЕМ МЕТКУ ПРОЗРАЧНОЙ ДЛЯ СОБЫТИЙ МЫШИ
            self.drop_label.bind('<Button-1>', lambda e: 'break')  # Блокируем клики
            self.drop_label.bind('<Enter>', lambda e: 'break')     # Блокируем события наведения
            
    def hide_drop_hint(self):
        """Скрывает подсказку о Drag&Drop"""
        self.drop_label.place_forget()
        
    def on_drop(self, event):
        """Обработчик события перетаскивания файла"""
        try:
            # Получаем путь к файлу
            file_path = event.data
            
            # Очищаем фигурные скобки (Windows)
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]
            
            self.log(f"Обнаружен файл: {file_path}")
            self.process_dropped_file(file_path)
            
        except Exception as e:
            self.log(f"Ошибка при обработке перетаскивания: {str(e)}")
            
    def process_dropped_file(self, file_path):
        """Обрабатывает перетащенный файл"""
        # Проверяем что файл существует
        if not os.path.exists(file_path):
            self.log("Ошибка: Файл не найден")
            return
            
        # Проверяем расширение файла
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in ['.html', '.htm']:
            self.process_html_file(file_path)
        elif file_ext in ['.txt']:
            self.process_text_file(file_path)
        else:
            messagebox.showwarning("Неверный формат", 
                                 "Поддерживаются только HTML (.html, .htm) и текстовые (.txt) файлы.\n"
                                 f"Ваш файл: {os.path.basename(file_path)}")
            
    def process_text_file(self, file_path):
        """Обрабатывает текстовый файл после перетаскивания"""
        try:
            self.log(f"Обработка текстового файла: {os.path.basename(file_path)}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            extracted_links = self.extract_urls_from_text(text_content)
            
            if extracted_links:
                # Добавляем найденные ссылки
                current_content = self.links_text.get(1.0, tk.END).strip()
                if current_content:
                    new_content = current_content + '\n' + '\n'.join(extracted_links)
                else:
                    new_content = '\n'.join(extracted_links)
                
                self.links_text.delete(1.0, tk.END)
                self.links_text.insert(1.0, new_content)
                self.hide_drop_hint()
                self.log(f"Из текстового файла извлечено {len(extracted_links)} ссылок")
            else:
                self.log("В текстовом файле не найдено ссылок Яндекс.Диска")
                
        except Exception as e:
            self.log(f"Ошибка при обработке текстового файла: {str(e)}")
            
    def paste_text_from_clipboard(self):
        """Вставляет текст из буфера обмена как есть"""
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
        """Извлекает ссылки из буфера обмена и вставляет только их"""
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
        """Загружает HTML файл и извлекает из него все ссылки"""
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
        
        # Паттерны для поиска ссылок
        patterns = [
            r'<a\s+[^>]*href\s*=\s*["\'](https?://[^"\']*yandex[^"\']*|https?://[^"\']*yadi\.sk[^"\']*)["\'][^>]*>',
            r'\[[^\]]*\]\((https?://[^)]*yandex[^)]*|https?://[^)]*yadi\.sk[^)]*)\)',
            r'(https?://[^\s<>"\'\(\)]*yandex[^\s<>"\'\(\)]*|https?://[^\s<>"\'\(\)]*yadi\.sk[^\s<>"\'\(\)]*)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(matches)
        
        # Фильтруем и очищаем ссылки
        valid_urls = []
        for url in set(urls):
            if any(domain in url for domain in ['yandex.ru', 'yandex.com', 'yadi.sk', 'disk.yandex']):
                clean_url = self.clean_url(url)
                if clean_url:
                    valid_urls.append(clean_url)
        
        return valid_urls
    
    def clean_url(self, url):
        """Очищает URL от лишних символов"""
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
        """Очищает только поле ссылок"""
        self.links_text.delete(1.0, tk.END)
        self.show_drop_hint()
            
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
            
    def clear_all(self):
        self.links_text.delete(1.0, tk.END)
        self.log_text.delete(1.0, tk.END)
        self.progress['value'] = 0
        self.stats_label.config(text="Готов к работе")
        self.show_drop_hint()
            
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    # Методы для работы с текстом и горячими клавишами
    def cut_text(self, event=None):
        """Вырезает выделенный текст"""
        try:
            focused_widget = self.root.focus_get()
            if focused_widget == self.links_text:
                self.links_text.event_generate("<<Cut>>")
                self.hide_drop_hint()  # Скрываем подсказку при вырезании
        except:
            pass
            
    def copy_text(self, event=None):
        """Копирует выделенный текст из поля ссылок"""
        try:
            focused_widget = self.root.focus_get()
            if focused_widget == self.links_text:
                self.links_text.event_generate("<<Copy>>")
        except:
            pass
            
    def copy_log_text(self, event=None):
        """Копирует выделенный текст из лога"""
        try:
            focused_widget = self.root.focus_get()
            if focused_widget == self.log_text:
                self.log_text.event_generate("<<Copy>>")
        except:
            pass
            
    def paste_text(self, event=None):
        """Вставляет текст в поле ссылок"""
        try:
            focused_widget = self.root.focus_get()
            if focused_widget == self.links_text:
                self.links_text.event_generate("<<Paste>>")
                self.hide_drop_hint()
        except:
            pass
            
    def select_all(self, event=None):
        """Выделяет весь текст в поле ссылок"""
        try:
            focused_widget = self.root.focus_get()
            if focused_widget == self.links_text:
                self.links_text.tag_add(tk.SEL, "1.0", tk.END)
                self.links_text.mark_set(tk.INSERT, "1.0")
                self.links_text.see(tk.INSERT)
        except:
            pass
            
    def select_all_log(self, event=None):
        """Выделяет весь текст в логе"""
        try:
            focused_widget = self.root.focus_get()
            if focused_widget == self.log_text:
                self.log_text.tag_add(tk.SEL, "1.0", tk.END)
                self.log_text.mark_set(tk.INSERT, "1.0")
                self.log_text.see(tk.INSERT)
        except:
            pass
            
    def clear_log(self):
        """Очищает лог"""
        self.log_text.delete(1.0, tk.END)
        
    def start_download(self):
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
        self.download_btn.button.config(state='disabled')
        
        thread = threading.Thread(target=self.download_files, args=(links, save_path))
        thread.daemon = True
        thread.start()
        
    def download_files(self, links, save_path):
        total_files = len(links)
        successful = 0
        failed = 0
        
        self.progress['maximum'] = total_files
        self.progress['value'] = 0
        
        self.log(f"Начало загрузки {total_files} файлов...")
        self.log(f"Папка сохранения: {save_path}")
        
        for i, link in enumerate(links):
            if not self.is_downloading:
                break
                
            try:
                self.stats_label.config(text=f"Обработка {i+1}/{total_files}")
                self.log(f"[{i+1}/{total_files}] Обработка: {link}")
                
                if self.download_file_correct(link, save_path):
                    successful += 1
                else:
                    failed += 1
                    
                self.progress['value'] = i + 1
                time.sleep(0.5)
                
            except Exception as e:
                failed += 1
                self.log(f"✗ Ошибка: {str(e)}")
                
        self.is_downloading = False
        self.download_btn.button.config(state='normal')
        self.stats_label.config(text=f"Завершено! Успешно: {successful}, Ошибок: {failed}")
        self.log(f"=== Загрузка завершена! Успешно: {successful}, Ошибок: {failed} ===")
        
        if successful > 0:
            messagebox.showinfo("Готово", f"Загрузка завершена!\nУспешно: {successful}\nОшибок: {failed}")
    
    def download_file_correct(self, public_key, save_path):
        """Скачивает файл используя API Яндекс.Диска"""
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
            
            # Если файл уже существует, добавляем номер
            counter = 1
            original_path = full_path
            while os.path.exists(full_path):
                name, ext = os.path.splitext(safe_filename)
                full_path = os.path.join(save_path, f"{name}_{counter}{ext}")
                counter += 1
            
            self.log(f"Скачивание: {safe_filename}")
            download_response = requests.get(download_url, stream=True, timeout=60)
            
            if download_response.status_code == 200:
                with open(full_path, 'wb') as f:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        if not self.is_downloading:
                            f.close()
                            if os.path.exists(full_path):
                                os.remove(full_path)
                            return False
                        if chunk:
                            f.write(chunk)
                
                self.log(f"✓ Успешно: {safe_filename}")
                return True
            else:
                self.log(f"Ошибка загрузки: {download_response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"Ошибка скачивания: {str(e)}")
            return False
    
    def get_filename_from_url(self, url):
        """Извлекает имя файла из URL"""
        try:
            decoded_url = unquote(url)
            if 'filename=' in decoded_url:
                filename_part = decoded_url.split('filename=')[1]
                return filename_part.split('&')[0]
            
            path = decoded_url.split('?')[0]
            filename = os.path.basename(path)
            return filename if filename and '.' in filename else None
        except:
            return None

def main():
    # Создаем корневое окно с поддержкой Drag&Drop если доступно
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = YandexDiskDownloader(root)
    root.mainloop()

if __name__ == "__main__":
    main()