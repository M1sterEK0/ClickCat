import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageOps
from pynput.mouse import Listener as MouseListener
from pynput.keyboard import Listener as KeyboardListener
import math
import sys
import os
from datetime import datetime
from screeninfo import get_monitors
import pygame  # Для работы со звуком
import random  # Для выбора случайного звука
import ctypes  # Для установки флага "всегда поверх"

# Функция для получения абсолютного пути к ресурсам
def resource_path(relative_path):
    """Получает абсолютный путь к ресурсам, как в разработке, так и в распакованном виде."""
    try:
        base_path = sys._MEIPASS  # Если программа запущена как исполняемый файл
    except Exception:
        base_path = os.path.abspath(".")  # Если программа запущена как скрипт
    return os.path.join(base_path, relative_path)

# Функция для установки окна поверх всех остальных
def set_window_always_on_top(hwnd):
    """Устанавливает окно поверх всех других."""
    user32 = ctypes.windll.user32
    hwnd = int(hwnd)  # Преобразуем hwnd в целое число
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004)

# Настройки окна
INITIAL_WIDTH = 320  # Исходная ширина изображения
INITIAL_HEIGHT = 370  # Исходная высота изображения
IMAGE_PATHS = [
    resource_path("image1.png"),
    resource_path("image2.png")
]  # Пути к вашим изображениям
SOUND_PATHS = [
    resource_path("sound1.wav"),
    resource_path("sound2.wav"),
    resource_path("sound3.wav")
]  # Пути к звуковым файлам
ANIMATION_DELAY = 100  # Задержка между кадрами анимации (в миллисекундах)
LOG_FILE = "key_press_log.txt"  # Файл для сохранения статистики
SETTINGS_FILE = "settings.txt"  # Файл для сохранения настроек
TRANSPARENT_COLOR = "#191970"  # Цвет, который будет прозрачным
BREATHING_PERIOD = 100  # Период "дыхания" в миллисекундах
BREATHING_AMPLITUDE = 2  # Амплитуда изменения размера

class KeyPressOverlay:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)  # Скрываем рамку окна
        self.root.attributes('-topmost', True)  # Окно всегда поверх других
        self.root.geometry(f"{INITIAL_WIDTH}x{INITIAL_HEIGHT}")  # Начальный размер окна
        self.root.configure(bg=TRANSPARENT_COLOR)  # Устанавливаем специальный цвет фона
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)  # Делаем этот цвет прозрачным

        # Устанавливаем окно поверх всех, включая панель задач
        hwnd = self.root.winfo_id()
        set_window_always_on_top(hwnd)

        # Новое множество для отслеживания нажатых клавиш
        self.pressed_keys = set()

        # Получаем размеры экрана
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # Инициализация текущих размеров окна
        self.current_width = INITIAL_WIDTH
        self.current_height = INITIAL_HEIGHT

        # Загрузка настроек с новыми значениями по умолчанию
        self.scale_factor = self.load_setting("scale_factor", 0.5)  # Значение по умолчанию: 0.5
        self.volume = self.load_setting("volume", 0.15)  # Значение по умолчанию: 0.15

        # Загрузка изображений с обработкой ошибок
        self.images = []
        for path in IMAGE_PATHS:
            try:
                self.images.append(Image.open(path))
            except Exception as e:
                print(f"Ошибка загрузки изображения {path}: {e}")
        if not self.images:
            raise FileNotFoundError("Не удалось загрузить ни одного изображения.")

        # Инициализация звуков
        pygame.mixer.init()
        self.sounds = []
        for path in SOUND_PATHS:
            if os.path.exists(path):
                try:
                    sound = pygame.mixer.Sound(path)
                    sound.set_volume(self.volume)
                    self.sounds.append(sound)
                except Exception as e:
                    print(f"Ошибка загрузки звука {path}: {e}")
            else:
                print(f"Файл звука не найден: {path}")
        if not self.sounds:
            print("Предупреждение: Не удалось загрузить ни одного звука.")

        self.current_image_index = 0

        # Создаем Label для отображения изображения без обводки
        self.label = tk.Label(
            root,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,  # Убираем обводку
            borderwidth=0,        # Убираем границу
            relief="flat"         # Убираем эффект рамки
        )
        self.label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)  # Центрируем изображение

        # Инициализация времени для эффекта "дыхания"
        self.breathing_time = 0

        # Счетчик нажатий
        self.key_press_count = self.load_key_press_count()  # Загружаем количество нажатий

        # Логгер для записи нажатий
        self.log_key_press(self.key_press_count)

        # Обработка нажатий клавиш и кнопок мыши
        self.keyboard_listener = KeyboardListener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener = MouseListener(on_click=self.on_mouse_click)
        self.keyboard_listener.start()
        self.mouse_listener.start()

        # Обработка перемещения окна при зажатии на картинку
        self._drag_data = {"x": 0, "y": 0}
        self.label.bind("<ButtonPress-1>", self.on_click_image)
        self.label.bind("<B1-Motion>", self.drag_window)

        # Кнопка меню (видна только при наведении мыши)
        self.menu_button = tk.Button(
            self.root,
            text="≡",
            font=("Arial", 12),
            bg="#4CAF50",
            activebackground="#4CAF50",
            bd=0,
            command=self.toggle_menu
        )
        self.menu_button.place(x=10, y=10, width=30, height=30)
        self.menu_button.lower()  # Сначала скрываем кнопку

        # Обработка наведения мыши
        self.root.bind("<Enter>", self.show_menu_button)
        self.root.bind("<Leave>", self.hide_menu_button)

        # Независимое выпадающее меню
        self.menu_window = None
        self.is_menu_open = False

        # Флаг для отзеркаливания изображения
        self.is_flipped = False

        # Установка первой картинки
        self.update_image()

        # Запуск эффекта "дыхания"
        self.start_breathing()

    def load_setting(self, key, default):
        """Загружает настройку из файла settings.txt."""
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                for line in f:
                    if line.startswith(f"{key}:"):
                        try:
                            return float(line.split(":")[1].strip())
                        except ValueError:
                            pass
        return default

    def save_settings(self):
        """Сохраняет настройки в файл settings.txt."""
        with open(SETTINGS_FILE, "w") as f:
            f.write(f"scale_factor: {self.scale_factor}\n")
            f.write(f"volume: {self.volume}\n")

    def load_key_press_count(self):
        """Загружает количество нажатий из файла key_press_log.txt."""
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                content = f.read().strip()
                if content.startswith("Number of clicks:"):
                    try:
                        return int(content.split(":")[1].strip())
                    except ValueError:
                        pass
        return 0

    def log_key_press(self, count):
        """Сохраняет количество нажатий в файл key_press_log.txt."""
        with open(LOG_FILE, "w") as f:
            f.write(f"Number of clicks: {count}")

    def update_image(self):
        """Обновляет изображение в label."""
        image = self.images[self.current_image_index]

        # Отзеркаливаем изображение, если флаг активен
        if self.is_flipped:
            image = ImageOps.mirror(image)

        # Вычисляем новые размеры с учетом масштабирования
        new_width = int(INITIAL_WIDTH * self.scale_factor)
        new_height = int(INITIAL_HEIGHT * self.scale_factor)

        # Масштабируем изображение
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized_image)

        # Обновляем label
        self.label.config(
            image=photo,
            bg=TRANSPARENT_COLOR,  # Убеждаемся, что фон совпадает с прозрачным цветом
            highlightthickness=0,  # Убираем обводку
            borderwidth=0,         # Убираем границу
            relief="flat"          # Убираем эффект рамки
        )
        self.label.image = photo

        # Обновляем размеры окна
        self.root.geometry(f"{new_width}x{new_height}")

    def start_breathing(self):
        """Запускает эффект 'дыхания'."""
        self.breathing_time += 1
        self.update_breathing_animation()
        self.root.after(8, self.start_breathing)

    def update_breathing_animation(self):
        """Обновляет анимацию 'дыхания'."""
        breathing_offset = BREATHING_AMPLITUDE * math.sin(2 * math.pi * self.breathing_time / BREATHING_PERIOD)
        new_height = int(INITIAL_HEIGHT * self.scale_factor + breathing_offset)
        new_width = int(INITIAL_WIDTH * self.scale_factor)
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        new_y = current_y + self.current_height - new_height
        self.root.geometry(f"{new_width}x{new_height}+{current_x}+{new_y}")
        self.current_height = new_height

        # Обновляем флаг "всегда поверх"
        hwnd = self.root.winfo_id()
        set_window_always_on_top(hwnd)

    def toggle_menu(self):
        """Показывает/скрывает выпадающее меню."""
        if not self.is_menu_open:
            self.menu_window = tk.Toplevel(self.root)
            self.menu_window.overrideredirect(True)
            self.menu_window.attributes('-topmost', True)
            self.menu_window.configure(bg="#212121")

            gradient_image = self.create_gradient(200, 250, "#E17954", "#E1B861")
            gradient_photo = ImageTk.PhotoImage(gradient_image)
            background_label = tk.Label(self.menu_window, image=gradient_photo, bg="#212121")
            background_label.image = gradient_photo
            background_label.place(x=0, y=0, relwidth=1, relheight=1)

            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            menu_width = 200
            menu_height = 250
            menu_x = main_x + self.root.winfo_width()
            menu_y = main_y
            if menu_x + menu_width > self.screen_width:
                menu_x = main_x - menu_width
            if menu_y + menu_height > self.screen_height:
                menu_y = main_y - menu_height
            self.menu_window.geometry(f"{menu_width}x{menu_height}+{menu_x}+{menu_y}")

            counter_label = tk.Label(self.menu_window, text=f"Clicks: {self.key_press_count}", bg="#212121", fg="white")
            counter_label.pack(side=tk.TOP, pady=10)

            flip_button = tk.Button(
                self.menu_window,
                text="Flip",
                bg="#FFC107",
                activebackground="#FFC107",
                bd=0,
                command=self.toggle_flip
            )
            flip_button.place(x=10, y=40)

            scale_frame = tk.Frame(self.menu_window, bg="#212121")
            scale_frame.place(x=10, y=80, width=180, height=50)

            scale_label = tk.Label(scale_frame, text="Scale:", bg="#212121", fg="white", anchor="w")
            scale_label.pack(side=tk.LEFT, padx=(0, 10))

            self.scale_slider = tk.Scale(
                scale_frame,
                from_=0.35,
                to=1.0,
                resolution=0.05,
                orient=tk.HORIZONTAL,
                length=120,
                bg="#212121",
                fg="white",
                highlightthickness=0,
                troughcolor="#424242",
                sliderrelief=tk.FLAT,
                command=self.update_scale
            )
            self.scale_slider.set(self.scale_factor)
            self.scale_slider.pack(side=tk.LEFT)

            volume_frame = tk.Frame(self.menu_window, bg="#212121")
            volume_frame.place(x=10, y=140, width=180, height=50)

            volume_label = tk.Label(volume_frame, text="Volume:", bg="#212121", fg="white", anchor="w")
            volume_label.pack(side=tk.LEFT, padx=(0, 10))

            self.volume_slider = tk.Scale(
                volume_frame,
                from_=0.0,
                to=1.0,
                resolution=0.05,
                orient=tk.HORIZONTAL,
                length=120,
                bg="#212121",
                fg="white",
                highlightthickness=0,
                troughcolor="#424242",
                sliderrelief=tk.FLAT,
                command=self.update_volume
            )
            self.volume_slider.set(self.volume)
            self.volume_slider.pack(side=tk.LEFT)

            exit_button = tk.Button(
                self.menu_window,
                text="Exit",
                bg="#FF5722",
                activebackground="#FF5722",
                bd=0,
                command=self.exit_app
            )
            exit_button.place(relx=0.5, rely=0.9, anchor=tk.CENTER)

            self.root.bind("<Button-1>", self.close_menu_if_outside)
            self.is_menu_open = True
        else:
            self.close_menu()

    def close_menu(self):
        """Закрывает выпадающее меню."""
        if self.menu_window:
            self.save_settings()
            self.menu_window.destroy()
            self.menu_window = None
            self.is_menu_open = False
            self.root.unbind("<Button-1>")  # Отменяем привязку события

    def close_menu_if_outside(self, event=None):
        """Закрывает меню, если клик совершен вне его области."""
        if self.menu_window and event:
            x, y = event.x_root, event.y_root
            menu_x = self.menu_window.winfo_x()
            menu_y = self.menu_window.winfo_y()
            menu_width = self.menu_window.winfo_width()
            menu_height = self.menu_window.winfo_height()
            if not (menu_x <= x <= menu_x + menu_width and menu_y <= y <= menu_y + menu_height):
                self.close_menu()

    def create_gradient(self, width, height, color1, color2):
        """Создает градиентное изображение."""
        image = Image.new("RGB", (width, height), color1)
        draw = ImageDraw.Draw(image)
        for i in range(height):
            r = int((i / height) * int(color2[1:3], 16) + (1 - i / height) * int(color1[1:3], 16))
            g = int((i / height) * int(color2[3:5], 16) + (1 - i / height) * int(color1[3:5], 16))
            b = int((i / height) * int(color2[5:7], 16) + (1 - i / height) * int(color1[5:7], 16))
            draw.line((0, i, width, i), fill=f"#{r:02x}{g:02x}{b:02x}")
        return image

    def update_scale(self, value):
        """Обновляет коэффициент масштабирования."""
        self.scale_factor = float(value)
        self.adjust_window_position()
        self.update_image()

    def update_volume(self, value):
        """Обновляет громкость звука."""
        self.volume = float(value)
        for sound in self.sounds:
            sound.set_volume(self.volume)

    def adjust_window_position(self):
        """Пересчитывает позицию окна для масштабирования относительно левого нижнего угла."""
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        new_height = int(INITIAL_HEIGHT * self.scale_factor)
        new_y = current_y + self.current_height - new_height
        self.root.geometry(f"+{current_x}+{new_y}")
        self.current_height = new_height

        # Обновляем флаг "всегда поверх"
        hwnd = self.root.winfo_id()
        set_window_always_on_top(hwnd)

    def toggle_flip(self):
        """Переключает отзеркаливание изображения."""
        self.is_flipped = not self.is_flipped
        self.update_image()

    def on_key_press(self, key):
        """Обработчик нажатия клавиш."""
        try:
            key_char = key.char
        except AttributeError:
            key_char = str(key)

        if key not in self.pressed_keys:
            self.pressed_keys.add(key)
            self.key_press_count += 1
            self.log_key_press(self.key_press_count)
            self.switch_to_second_image()
            self.play_random_sound()

    def on_key_release(self, key):
        """Обработчик отпускания клавиш."""
        try:
            key_char = key.char
        except AttributeError:
            key_char = str(key)

        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
            self.restore_first_image()

    def on_mouse_click(self, x, y, button, pressed):
        """Обработчик нажатия кнопок мыши."""
        if pressed:
            self.key_press_count += 1
            self.log_key_press(self.key_press_count)
            self.switch_to_second_image()
            self.play_random_sound()
        else:
            self.restore_first_image()

    def switch_to_second_image(self):
        """Переключает изображение на второе."""
        self.current_image_index = 1
        self.update_image()

    def restore_first_image(self):
        """Восстанавливает первое изображение."""
        self.current_image_index = 0
        self.update_image()

    def play_random_sound(self):
        """Воспроизводит случайный звук из списка."""
        if self.sounds:
            sound = random.choice(self.sounds)
            sound.play()

    def show_menu_button(self, event):
        """Показывает кнопку меню при наведении мыши."""
        self.menu_button.lift()

    def hide_menu_button(self, event):
        """Скрывает кнопку меню при уходе мыши."""
        self.menu_button.lower()

    def on_click_image(self, event):
        """Начинает перемещение окна при нажатии на изображение."""
        self._drag_data["x"] = event.x_root - self.root.winfo_x()
        self._drag_data["y"] = event.y_root - self.root.winfo_y()

    def drag_window(self, event):
        """Перемещает окно при удержании левой кнопки мыши."""
        new_x = event.x_root - self._drag_data["x"]
        new_y = event.y_root - self._drag_data["y"]

        # Получаем все подключённые мониторы
        monitors = get_monitors()

        if not monitors:
            return  # Нет мониторов — ничего не делаем

        # Находим минимальную и максимальную координату по X и Y
        min_x = min(m.x for m in monitors)
        min_y = min(m.y for m in monitors)
        max_x = max(m.x + m.width for m in monitors)
        max_y = max(m.y + m.height for m in monitors)

        # Ширина и высота окна
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        # Ограничиваем новую позицию внутри объединённой области экранов
        new_x = max(min_x, min(new_x, max_x - window_width))
        new_y = max(min_y, min(new_y, max_y - window_height))

        # Применяем новую позицию
        self.root.geometry(f"+{new_x}+{new_y}")

        # Обновляем флаг "всегда поверх"
        hwnd = self.root.winfo_id()
        set_window_always_on_top(hwnd)

    def exit_app(self):
        """Закрывает приложение."""
        self.keyboard_listener.stop()
        self.mouse_listener.stop()
        self.save_settings()
        pygame.quit()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = KeyPressOverlay(root)
    root.mainloop()