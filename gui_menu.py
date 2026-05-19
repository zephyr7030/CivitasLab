import tkinter as tk
from tkinter import ttk, messagebox

from config import PROJECT_NAME


class MainMenuWindow:
    """项目开始界面。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(PROJECT_NAME)
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1280x720")
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.build_ui()

    def build_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)
        main.rowconfigure(2, weight=1)
        main.columnconfigure(0, weight=1)

        title_frame = ttk.Frame(main)
        title_frame.grid(row=0, column=0, sticky="s", pady=30)
        ttk.Label(title_frame, text=PROJECT_NAME, font=("Microsoft YaHei", 42, "bold")).pack()
        ttk.Label(
            title_frame,
            text="多部族 · 遗传变异 · 资源竞争 · 道德演化 · 社会行为模拟",
            font=("Microsoft YaHei", 16),
        ).pack(pady=16)

        button_frame = ttk.Frame(main)
        button_frame.grid(row=1, column=0)
        for text, command in [
            ("介绍", self.show_intro),
            ("开始", self.start_config),
            ("关于项目", self.show_about),
            ("退出", self.exit_app),
        ]:
            ttk.Button(button_frame, text=text, width=24, command=command).pack(pady=8)

        ttk.Label(main, text="BOT8 Simulation System", font=("Microsoft YaHei", 10)).grid(row=2, column=0, sticky="n", pady=30)

    def show_intro(self):
        messagebox.showinfo(
            "介绍",
            (
                f"{PROJECT_NAME}\n\n"
                "这是一个用于观察多部族生物/社会演化的模拟模型。\n\n"
                "核心内容包括：\n"
                "1. 支持最多10个部族，默认3个部族。\n"
                "2. 每个部族拥有独立环境资源、政府存款和部族参数。\n"
                "3. 个体拥有道德、武力、智慧、繁殖倾向、劳动意愿、存款、寿命等属性。\n"
                "4. 环境资源通过劳动转化为社会财富。\n"
                "5. 部族内存在掠夺、治安制裁、政府救助、个体救助。\n"
                "6. 部族间存在侵略机制。\n"
                "7. 新生个体会继承母代属性并发生变异。\n"
                "8. 可开启进化机制，依据收益表现影响后代方向。"
            ),
        )

    def show_about(self):
        messagebox.showinfo(
            "关于项目",
            (
                f"{PROJECT_NAME}\n\n"
                "项目定位：\n"
                "用于探索资源、道德、能力、繁殖、劳动、掠夺、救助、政府存款和进化方向之间关系的实验模型。\n\n"
                "当前版本特点：\n"
                "支持1-10个部族、启动前参数设置、参数记忆、机制开关、机制回合调度、实时 GUI、Excel / CSV 输出。"
            ),
        )

    def start_config(self):
        from gui_settings import StartConfigWindow
        self.root.destroy()
        StartConfigWindow().run()

    def exit_app(self):
        self.root.destroy()
        raise SystemExit

    def run(self):
        self.root.mainloop()
