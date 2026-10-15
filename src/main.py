import queue
import pygame

from sender import Sender


WIDTH, HEIGHT = 800, 600
FPS = 60

BG = (24, 28, 38)
PANEL = (38, 44, 58)
WHITE = (240, 242, 247)
GREY = (160, 170, 185)
GREEN = (65, 175, 105)
RED = (205, 55, 60)
BLUE = (65, 115, 195)


class Button:
    def __init__(self, rect, text, color):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color

    def draw(self, surface, font, enabled=True):
        color = self.color if enabled else (75, 78, 86)

        pygame.draw.rect(
            surface, color, self.rect, border_radius=10
        )

        label = font.render(self.text, True, WHITE)
        surface.blit(
            label,
            label.get_rect(center=self.rect.center),
        )

    def clicked(self, pos):
        return self.rect.collidepoint(pos)


class App:
    def __init__(self):
        pygame.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Boom Sender")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 21)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.title_font = pygame.font.SysFont("arial", 36, bold=True)

        self.sender = Sender()
        self.events = queue.Queue()

        self.status = "Нажми «Найти город»."
        self.selected_index = -1
        self.devices = []

        self.scan_button = Button(
            (40, 125, 720, 50), "Найти город", BLUE
        )
        self.connect_button = Button(
            (40, 490, 350, 55), "Подключиться", GREEN
        )
        self.boom_button = Button(
            (410, 490, 350, 55), "ВЗОРВАТЬ", RED
        )

    def draw_text(self, text, x, y, color=WHITE, font=None):
        font = font or self.font
        image = font.render(text, True, color)
        self.screen.blit(image, (x, y))

    def draw(self):
        self.screen.fill(BG)

        self.draw_text(
            "ЯДЕРНЫЙ ЧЕМОДАНЧИК", 40, 35, WHITE, self.title_font
        )
        self.draw_text(
            "Управление городами в локальной сети",
            42, 82, GREY, self.small_font
        )

        self.scan_button.draw(
            self.screen, self.font, not self.sender.busy
        )

        pygame.draw.rect(
            self.screen, PANEL, (40, 195, 720, 260),
            border_radius=12,
        )

        self.draw_text("Найденные города", 60, 210)

        if not self.devices:
            self.draw_text(
                "Пока ничего не найдено.",
                60, 255, GREY, self.small_font
            )

        for index, device in enumerate(self.devices):
            rect = pygame.Rect(55, 250 + index * 48, 690, 40)

            color = (
                BLUE if index == self.selected_index
                else (49, 56, 72)
            )

            pygame.draw.rect(
                self.screen, color, rect, border_radius=6
            )

            label = (
                f'{device["name"]}  '
                f'{device["ip"]}:{device["port"]}'
            )

            self.draw_text(
                label, 68, rect.y + 9, WHITE, self.small_font
            )

        connected = self.sender.connected_device is not None

        self.connect_button.draw(
            self.screen,
            self.font,
            not self.sender.busy and self.selected_index >= 0,
        )
        self.boom_button.draw(
            self.screen,
            self.font,
            not self.sender.busy and connected,
        )

        self.draw_text(
            f"Статус: {self.status}",
            40, 565, GREY, self.small_font
        )

        pygame.display.flip()

    def scan(self):
        self.devices = []
        self.selected_index = -1
        self.status = "Ищем Receiver..."

        started = self.sender.scan(
            lambda devices, error: self.events.put(
                ("scan", devices, error)
            )
        )

        if not started:
            self.status = "слишком много запросов, хватит."

    def connect(self):
        if not 0 <= self.selected_index < len(self.devices):
            return

        device = self.devices[self.selected_index]
        self.status = "Подключаемся..."

        started = self.sender.connect(
            device,
            lambda ok, message: self.events.put(
                ("result", ok, message)
            ),
        )

        if not started:
            self.status = "не торопись."

    def explode(self):
        self.status = "Отправляем ядерку..."

        started = self.sender.explode(
            lambda ok, message: self.events.put(
                ("result", ok, message)
            )
        )

        if not started:
            self.status = "не торопись."

    def process_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            if event[0] == "scan":
                _, devices, error = event
                self.devices = devices

                if error:
                    self.status = f"Ошибка поиска: {error}"
                elif devices:
                    self.status = f"Найдено городов: {len(devices)}"
                else:
                    self.status = "Receiver не найден."

            elif event[0] == "result":
                _, ok, message = event
                self.status = message

                if not ok:
                    self.sender.disconnect()

    def handle_click(self, pos):
        if self.scan_button.clicked(pos):
            self.scan()
            return

        if self.connect_button.clicked(pos):
            self.connect()
            return

        if self.boom_button.clicked(pos):
            self.explode()
            return

        for index, _ in enumerate(self.devices):
            rect = pygame.Rect(55, 250 + index * 48, 690, 40)

            if rect.collidepoint(pos):
                self.selected_index = index
                self.status = (
                    f'Выбрано: {self.devices[index]["name"]}'
                )
                return

    def run(self):
        running = True

        while running:
            self.clock.tick(FPS)
            self.process_events()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.handle_click(event.pos)

            self.draw()

        pygame.quit()


if __name__ == "__main__":
    App().run()