import random
import sys

import pygame

# 화면 및 격자 설정
CELL_SIZE = 20
GRID_WIDTH = 30
GRID_HEIGHT = 20
WIDTH = CELL_SIZE * GRID_WIDTH
HEIGHT = CELL_SIZE * GRID_HEIGHT
FPS = 10

# 색상
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 200, 0)
DARK_GREEN = (0, 120, 0)
CYAN = (0, 200, 200)
DARK_CYAN = (0, 120, 120)
RED = (200, 0, 0)
GRAY = (40, 40, 40)

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
DIRECTIONS = (UP, DOWN, LEFT, RIGHT)
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}


def random_food_position(occupied):
    while True:
        pos = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
        if pos not in occupied:
            return pos


def draw_cell(surface, pos, color):
    rect = pygame.Rect(pos[0] * CELL_SIZE, pos[1] * CELL_SIZE, CELL_SIZE, CELL_SIZE)
    pygame.draw.rect(surface, color, rect)


def draw_grid(surface):
    for x in range(0, WIDTH, CELL_SIZE):
        pygame.draw.line(surface, GRAY, (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, CELL_SIZE):
        pygame.draw.line(surface, GRAY, (0, y), (WIDTH, y))


def show_message(surface, font, text, y_offset=0):
    rendered = font.render(text, True, WHITE)
    rect = rendered.get_rect(center=(WIDTH // 2, HEIGHT // 2 + y_offset))
    surface.blit(rendered, rect)


class Snake:
    def __init__(self, body, direction, color, head_color):
        self.body = body
        self.direction = direction
        self.next_direction = direction
        self.color = color
        self.head_color = head_color
        self.alive = True
        self.score = 0

    def turn(self, new_direction):
        if new_direction != OPPOSITE[self.direction]:
            self.next_direction = new_direction

    def planned_head(self):
        dx, dy = self.next_direction
        head_x, head_y = self.body[0]
        return (head_x + dx, head_y + dy)

    def apply_move(self, new_head, grew):
        self.direction = self.next_direction
        self.body.insert(0, new_head)
        if not grew:
            self.body.pop()

    def draw(self, surface):
        for segment in self.body[1:]:
            draw_cell(surface, segment, self.color)
        draw_cell(surface, self.body[0], self.head_color)


def is_wall_collision(pos):
    return pos[0] < 0 or pos[0] >= GRID_WIDTH or pos[1] < 0 or pos[1] >= GRID_HEIGHT


def choose_ai_direction(ai_snake, other_snake, food):
    """사과까지의 거리를 최소화하는 방향을 선택하되, 벽/뱀 몸통 충돌은 피한다."""
    obstacles = set(ai_snake.body[:-1]) | set(other_snake.body[:-1])
    head_x, head_y = ai_snake.body[0]

    candidates = []
    for direction in DIRECTIONS:
        if direction == OPPOSITE[ai_snake.direction]:
            continue
        dx, dy = direction
        new_head = (head_x + dx, head_y + dy)
        if is_wall_collision(new_head) or new_head in obstacles:
            continue
        distance = abs(new_head[0] - food[0]) + abs(new_head[1] - food[1])
        candidates.append((distance, direction))

    if not candidates:
        return ai_snake.direction

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake - Human vs AI")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("malgungothic", 28)
    small_font = pygame.font.SysFont("malgungothic", 20)

    while True:
        result = run_game(screen, clock, font, small_font)
        if result == "quit":
            break


def run_game(screen, clock, font, small_font):
    human = Snake(
        body=[(GRID_WIDTH // 4, GRID_HEIGHT // 2)],
        direction=RIGHT,
        color=DARK_GREEN,
        head_color=GREEN,
    )
    ai = Snake(
        body=[(GRID_WIDTH * 3 // 4, GRID_HEIGHT // 2)],
        direction=LEFT,
        color=DARK_CYAN,
        head_color=CYAN,
    )
    food = random_food_position(human.body + ai.body)
    game_over = False
    result_message = ""

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "quit"
                if not game_over:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        human.turn(UP)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        human.turn(DOWN)
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        human.turn(LEFT)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        human.turn(RIGHT)
                else:
                    if event.key == pygame.K_r:
                        return "restart"

        if not game_over:
            ai.turn(choose_ai_direction(ai, human, food))

            human_new_head = human.planned_head()
            ai_new_head = ai.planned_head()

            # 이번 턴 이동 전 몸통(꼬리는 이동하며 비워지므로 충돌 판정에서 제외)
            human_body_static = set(human.body[:-1])
            ai_body_static = set(ai.body[:-1])

            human_dies = (
                is_wall_collision(human_new_head)
                or human_new_head in human_body_static
                or human_new_head in ai_body_static
                or human_new_head == ai_new_head
            )
            ai_dies = (
                is_wall_collision(ai_new_head)
                or ai_new_head in ai_body_static
                or ai_new_head in human_body_static
                or ai_new_head == human_new_head
            )

            if human_dies:
                human.alive = False
            if ai_dies:
                ai.alive = False

            if not human_dies:
                grew = human_new_head == food
                human.apply_move(human_new_head, grew)
                if grew:
                    human.score += 1

            if not ai_dies:
                grew = ai_new_head == food
                ai.apply_move(ai_new_head, grew)
                if grew:
                    ai.score += 1

            # 두 뱀이 같은 턴에 사과를 먹으면 새 사과 하나만 생성
            if (not human_dies and human_new_head == food) or (
                not ai_dies and ai_new_head == food
            ):
                food = random_food_position(human.body + ai.body)

            if not human.alive or not ai.alive:
                game_over = True
                if not human.alive and not ai.alive:
                    if human.score == ai.score:
                        result_message = "무승부!"
                    elif human.score > ai.score:
                        result_message = "사람 승리! (동시 충돌)"
                    else:
                        result_message = "AI 승리! (동시 충돌)"
                elif not human.alive:
                    result_message = "AI 승리!"
                else:
                    result_message = "사람 승리!"

        screen.fill(BLACK)
        draw_grid(screen)
        human.draw(screen)
        ai.draw(screen)
        draw_cell(screen, food, RED)

        score_text = small_font.render(
            f"사람: {human.score}   AI: {ai.score}", True, WHITE
        )
        screen.blit(score_text, (5, 5))

        if game_over:
            show_message(screen, font, result_message, -10)
            show_message(screen, small_font, "R: 재시작, ESC: 종료", 25)

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
    pygame.quit()
    sys.exit()
