import tkinter as tk
import random

WIDTH = 480
HEIGHT = 600

PADDLE_WIDTH = 80
PADDLE_HEIGHT = 12
PADDLE_SPEED = 8

BALL_SIZE = 12
BALL_SPEED = 5

BRICK_ROWS = 6
BRICK_COLS = 8
BRICK_WIDTH = WIDTH // BRICK_COLS
BRICK_HEIGHT = 24
BRICK_TOP_MARGIN = 50

BRICK_COLORS = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#3498db", "#9b59b6"]


class BreakoutGame:
    def __init__(self, root):
        self.root = root
        self.root.title("블럭깨기")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="black", highlightthickness=0)
        self.canvas.pack()

        self.root.bind("<Left>", self.move_left)
        self.root.bind("<Right>", self.move_right)
        self.root.bind("<a>", self.move_left)
        self.root.bind("<d>", self.move_right)
        self.root.bind("<space>", self.on_space)

        self.moving_left = False
        self.moving_right = False
        self.root.bind("<KeyPress-Left>", lambda e: self.set_move("left", True))
        self.root.bind("<KeyRelease-Left>", lambda e: self.set_move("left", False))
        self.root.bind("<KeyPress-Right>", lambda e: self.set_move("right", True))
        self.root.bind("<KeyRelease-Right>", lambda e: self.set_move("right", False))
        self.root.bind("<KeyPress-a>", lambda e: self.set_move("left", True))
        self.root.bind("<KeyRelease-a>", lambda e: self.set_move("left", False))
        self.root.bind("<KeyPress-d>", lambda e: self.set_move("right", True))
        self.root.bind("<KeyRelease-d>", lambda e: self.set_move("right", False))

        self.game_running = False
        self.game_over = False
        self.game_won = False
        self.score = 0
        self.lives = 3

        self.reset_game()
        self.update_loop()

    def set_move(self, direction, value):
        if direction == "left":
            self.moving_left = value
        else:
            self.moving_right = value

    def move_left(self, event=None):
        pass

    def move_right(self, event=None):
        pass

    def on_space(self, event=None):
        if not self.game_running:
            if self.game_over or self.game_won:
                self.reset_game()
            self.game_running = True

    def reset_game(self):
        self.canvas.delete("all")
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.game_won = False
        self.game_running = False

        paddle_x = (WIDTH - PADDLE_WIDTH) / 2
        paddle_y = HEIGHT - 40
        self.paddle = self.canvas.create_rectangle(
            paddle_x, paddle_y, paddle_x + PADDLE_WIDTH, paddle_y + PADDLE_HEIGHT,
            fill="white", outline=""
        )

        self.reset_ball()
        self.create_bricks()

        self.score_text = self.canvas.create_text(
            10, 10, anchor="nw", fill="white", font=("Arial", 12),
            text=f"점수: {self.score}"
        )
        self.lives_text = self.canvas.create_text(
            WIDTH - 10, 10, anchor="ne", fill="white", font=("Arial", 12),
            text=f"생명: {self.lives}"
        )
        self.message_text = self.canvas.create_text(
            WIDTH / 2, HEIGHT / 2, fill="yellow", font=("Arial", 18, "bold"),
            text="스페이스바를 눌러 시작하세요"
        )

    def reset_ball(self):
        if hasattr(self, "ball"):
            self.canvas.delete(self.ball)
        x = WIDTH / 2
        y = HEIGHT - 60
        self.ball = self.canvas.create_oval(
            x - BALL_SIZE / 2, y - BALL_SIZE / 2, x + BALL_SIZE / 2, y + BALL_SIZE / 2,
            fill="yellow", outline=""
        )
        self.ball_dx = random.choice([-1, 1]) * BALL_SPEED
        self.ball_dy = -BALL_SPEED

    def create_bricks(self):
        self.bricks = []
        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                x1 = col * BRICK_WIDTH + 2
                y1 = row * BRICK_HEIGHT + BRICK_TOP_MARGIN
                x2 = x1 + BRICK_WIDTH - 4
                y2 = y1 + BRICK_HEIGHT - 4
                color = BRICK_COLORS[row % len(BRICK_COLORS)]
                brick = self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
                self.bricks.append(brick)

    def update_loop(self):
        if self.game_running:
            self.move_paddle()
            self.move_ball()
        self.root.after(16, self.update_loop)

    def move_paddle(self):
        coords = self.canvas.coords(self.paddle)
        dx = 0
        if self.moving_left:
            dx -= PADDLE_SPEED
        if self.moving_right:
            dx += PADDLE_SPEED
        if dx != 0:
            if coords[0] + dx < 0:
                dx = -coords[0]
            if coords[2] + dx > WIDTH:
                dx = WIDTH - coords[2]
            self.canvas.move(self.paddle, dx, 0)

    def move_ball(self):
        self.canvas.move(self.ball, self.ball_dx, self.ball_dy)
        bx1, by1, bx2, by2 = self.canvas.coords(self.ball)

        if bx1 <= 0 or bx2 >= WIDTH:
            self.ball_dx *= -1
        if by1 <= 0:
            self.ball_dy *= -1

        if by2 >= HEIGHT:
            self.lose_life()
            return

        px1, py1, px2, py2 = self.canvas.coords(self.paddle)
        if by2 >= py1 and by1 <= py2 and bx2 >= px1 and bx1 <= px2 and self.ball_dy > 0:
            hit_pos = ((bx1 + bx2) / 2 - px1) / PADDLE_WIDTH
            self.ball_dx = BALL_SPEED * (hit_pos - 0.5) * 2.5
            self.ball_dy = -abs(self.ball_dy)

        hit_brick = None
        for brick in self.bricks:
            coords = self.canvas.coords(brick)
            if not coords:
                continue
            rx1, ry1, rx2, ry2 = coords
            if bx2 >= rx1 and bx1 <= rx2 and by2 >= ry1 and by1 <= ry2:
                hit_brick = brick
                break

        if hit_brick:
            rx1, ry1, rx2, ry2 = self.canvas.coords(hit_brick)
            self.canvas.delete(hit_brick)
            self.bricks.remove(hit_brick)
            self.score += 10
            self.canvas.itemconfig(self.score_text, text=f"점수: {self.score}")

            overlap_left = bx2 - rx1
            overlap_right = rx2 - bx1
            overlap_top = by2 - ry1
            overlap_bottom = ry2 - by1
            min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
            if min_overlap in (overlap_left, overlap_right):
                self.ball_dx *= -1
            else:
                self.ball_dy *= -1

            if not self.bricks:
                self.win_game()

    def lose_life(self):
        self.lives -= 1
        self.canvas.itemconfig(self.lives_text, text=f"생명: {self.lives}")
        self.game_running = False
        if self.lives <= 0:
            self.end_game(win=False)
        else:
            self.reset_ball()
            self.canvas.itemconfig(self.message_text, text="스페이스바를 눌러 계속하세요")
            self.canvas.itemconfig(self.message_text, state="normal")

    def win_game(self):
        self.win = True
        self.end_game(win=True)

    def end_game(self, win):
        self.game_running = False
        self.game_over = not win
        self.game_won = win
        text = "승리! 스페이스바로 재시작" if win else "게임 오버! 스페이스바로 재시작"
        self.canvas.itemconfig(self.message_text, text=text, state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    game = BreakoutGame(root)
    root.mainloop()
