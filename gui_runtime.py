import copy
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from config import PROJECT_NAME
from settings_io import normalize_settings, get_active_population_names
from model import Environment
from output import save_outputs, OUTPUT_XLSX_NAME, OUTPUT_CSV_NAME


class RuntimeWindow:
    """运行界面。

    负责：
    1. 每回合驱动 Environment.run_turn()。
    2. 刷新汇总数据与部族数据。
    3. 处理暂停、返回设置、重新运行、退出等 GUI 操作。

    BOT8 2.2.0：根据后续 GUI 将全面重写的开发规则，删除现有所有折线图代码，
    暂时只保留数据表格和必要控制按钮。
    """

    def __init__(self, settings):
        self.settings = normalize_settings(copy.deepcopy(settings))
        self.population_names = get_active_population_names(self.settings)
        self.env = Environment(self.settings)

        self.root = tk.Tk()
        self.root.title(f"{PROJECT_NAME} - 运行中")
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1600x900")
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        self.is_running = True
        self.is_paused = False
        self.finish_dialog_open = False

        self.build_ui()

    def build_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1, minsize=420)
        main.rowconfigure(0, weight=1)

        content = ttk.Frame(main)
        content.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        content.columnconfigure(0, weight=1)
        for row, weight in [(0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (5, 0), (6, 3), (7, 0), (8, 2)]:
            content.rowconfigure(row, weight=weight)

        ttk.Label(content, text=PROJECT_NAME, font=("Microsoft YaHei", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.turn_label = ttk.Label(content, text="TURN 0", font=("Microsoft YaHei", 12, "bold"))
        self.turn_label.grid(row=1, column=0, sticky="w", pady=(0, 8))

        button_frame = ttk.Frame(content)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.pause_button = ttk.Button(button_frame, text="暂停", command=self.toggle_pause)
        self.pause_button.pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="返回", command=self.return_to_settings).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="退出", command=self.exit_app).pack(side="left")

        ttk.Label(content, text="总览", font=("Microsoft YaHei", 12, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.overview_tree = ttk.Treeview(content, columns=["指标", "数值"], show="headings", height=10)
        for column in ["指标", "数值"]:
            self.overview_tree.heading(column, text=column)
            self.overview_tree.column(column, anchor="center", width=180)
        self.overview_tree.grid(row=4, column=0, sticky="nsew", pady=(0, 8))

        ttk.Label(content, text="部族数据", font=("Microsoft YaHei", 12, "bold")).grid(row=5, column=0, sticky="w", pady=(0, 4))
        columns = ["指标"] + self.population_names
        self.population_tree = ttk.Treeview(content, columns=columns, show="headings", height=18)
        for column in columns:
            self.population_tree.heading(column, text=column)
            self.population_tree.column(column, anchor="center", width=90)
        self.population_tree.grid(row=6, column=0, sticky="nsew")

        ttk.Label(content, text="实时阶段日志", font=("Microsoft YaHei", 12, "bold")).grid(row=7, column=0, sticky="w", pady=(8, 4))
        self.log_text = ScrolledText(content, height=10, wrap="word")
        self.log_text.grid(row=8, column=0, sticky="nsew")
        self.last_log_count = 0

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_button.config(text="继续" if self.is_paused else "暂停")
        if not self.is_paused:
            self.root.after(1, self.step)

    def update_tree_rows(self, tree, prefix, rows):
        """按固定行号更新 Treeview，避免每回合删除并重建整张表。"""
        for index, values in enumerate(rows):
            item_id = f"{prefix}{index}"
            if tree.exists(item_id):
                tree.item(item_id, values=values)
            else:
                tree.insert("", "end", iid=item_id, values=values)

        existing = list(tree.get_children())
        for item_id in existing[len(rows):]:
            tree.delete(item_id)

    def update_left_panel(self):
        overview = self.env.get_overview()
        overview_items = [
            ("回合", overview["Turn"]),
            ("启用部族数", overview["PopulationTypes"]),
            ("总个体数", overview["TotalPopulation"]),
            ("社会总财富", overview["TotalSocialWealth"]),
            ("环境总资源", overview["TotalEnvResource"]),
            ("平均环境健康", overview["AvgEnvHealth"]),
            ("平均资源压力", overview["AvgResourcePressure"]),
            ("平均社会信任", overview.get("AvgTrust", 0)),
            ("共用资源", "是" if overview.get("SharedEnvEnabled", 0) else "否"),
            ("政府总存款", overview["TotalGovernmentDeposit"]),
            ("总食物", overview.get("TotalFood", 0)),
            ("公司总货币", overview.get("TotalCompanyMoney", 0)),
            ("公司总库存", overview.get("TotalCompanyStock", 0)),
            ("总医疗用品", overview.get("TotalMedicalGoods", 0)),
            ("总教育用品", overview.get("TotalEducationGoods", 0)),
            ("总生育用品", overview.get("TotalReproductionGoods", 0)),
            ("本回合总生产", overview["TotalProduction"]),
            ("本回合侵略收益", overview["TotalInvasionGain"]),
            ("部族内掠夺损耗", overview["TotalInternalPlunderLoss"]),
            ("部族间侵略损耗", overview["TotalInvasionLoss"]),
            ("生存消耗", overview["TotalSurvivalCost"]),
        ]
        self.update_tree_rows(self.overview_tree, "overview_", overview_items)

        rows = {row["Population"]: row for row in self.env.get_population_summary_rows()}
        metrics = [
            ("个体数", "PopCount"),
            ("共用资源", "SharedEnvEnabled"),
            ("灾害发生", "DisasterOccurred"),
            ("灾害类型", "DisasterType"),
            ("灾害强度", "DisasterStrength"),
            ("环境资源", "EnvResource"),
            ("环境承载力", "EnvCapacity"),
            ("环境健康", "EnvHealth"),
            ("资源压力", "ResourcePressure"),
            ("实际再生", "ResourceRegenActual"),
            ("环境消耗", "EnvConsumption"),
            ("政府存款", "GovernmentDeposit"),
            ("食物总量", "TotalFood"),
            ("医疗用品总量", "TotalMedicalGoods"),
            ("教育用品总量", "TotalEducationGoods"),
            ("生育用品总量", "TotalReproductionGoods"),
            ("工具总量", "TotalTools"),
            ("政府食物", "GovernmentFood"),
            ("政府医疗用品", "GovernmentMedicalGoods"),
            ("公司货币", "CompanyMoneyTotal"),
            ("公司库存", "CompanyGoodsStockTotal"),
            ("公司工资", "CompanyWagesPaid"),
            ("公司销售收入", "CompanySalesIncome"),
            ("食物价格", "FoodPriceIndex"),
            ("食物需求", "FoodDemand"),
            ("食物供给", "FoodSupply"),
            ("食物未满足需求", "FoodUnmetDemand"),
            ("医疗价格", "MedicalGoodsPriceIndex"),
            ("医疗需求", "MedicalGoodsDemand"),
            ("医疗供给", "MedicalGoodsSupply"),
            ("医疗未满足需求", "MedicalGoodsUnmetDemand"),
            ("食物短缺数", "FoodShortageCount"),
            ("医疗短缺数", "MedicalShortageCount"),
            ("生病数", "SickCount"),
            ("新生病数", "NewSickCount"),
            ("医疗水平", "MedicalLevel"),
            ("救助预算已用", "GovAidBudgetUsed"),
            ("救助预算剩余", "GovAidBudgetRemaining"),
            ("治安度", "Security"),
            ("社会信任", "Trust"),
            ("信任变化", "TrustChange"),
            ("濒死数", "CriticalCount"),
            ("贫困层", "PoorCount"),
            ("低产层", "LowerCount"),
            ("普通层", "MiddleCount"),
            ("富裕层", "RichCount"),
            ("上升流动率", "UpwardMobilityRate"),
            ("下降流动率", "DownwardMobilityRate"),
            ("总存款", "TotalBalance"),
            ("平均存款", "AvgBalance"),
            ("平均智慧", "AvgIntelligence"),
            ("平均武力", "AvgStrength"),
            ("平均道德", "AvgMorality"),
            ("平均生育", "AvgReproduce"),
            ("平均劳动", "AvgLabor"),
            ("死亡均寿", "AvgDeadLifeSpan"),
            ("基尼系数", "Gini"),
            ("实物税", "GoodsTaxTotal"),
            ("财富税", "WealthTaxTotal"),
            ("政府救助", "GovernmentAidTotal"),
            ("劳动人数", "LaborWorkerCount"),
            ("出生数", "BirthCount"),
            ("死亡数", "DeathCount"),
        ]
        population_rows = []
        for label, key in metrics:
            values = [label]
            for population_name in self.population_names:
                value = rows[population_name][key]
                values.append(f"{value:.4f}" if key in {"Gini", "ResourcePressure", "Trust", "TrustChange", "UpwardMobilityRate", "DownwardMobilityRate"} else value)
            population_rows.append(values)
        self.update_tree_rows(self.population_tree, "population_", population_rows)

        if hasattr(self, "log_text"):
            logs = getattr(self.env, "event_logs", [])
            if len(logs) != self.last_log_count:
                self.log_text.delete("1.0", "end")
                self.log_text.insert("end", "\n".join(logs[-200:]))
                self.log_text.see("end")
                self.last_log_count = len(logs)

        self.turn_label.config(text=f"第 {self.env.turn} 回合")

    def step(self):
        if not self.is_running or self.is_paused:
            return
        try:
            if sum(len(value) for value in self.env.populations.values()) <= 0:
                self.finish()
                return
            if self.env.turn >= self.settings["base"]["max_turns"]:
                self.finish()
                return

            self.env.run_turn()
            self.update_left_panel()

            if self.env.turn % max(1, self.settings["base"]["save_interval"]) == 0:
                save_outputs(self.env)
        except Exception as exc:
            self.is_running = False
            messagebox.showerror("运行错误", f"模型运行时出现错误：\n\n{exc}")
            return

        self.root.after(1, self.step)

    def finish(self):
        if self.finish_dialog_open:
            return
        self.is_running = False
        save_outputs(self.env)
        self.finish_dialog_open = True
        self.show_finish_dialog()

    def show_finish_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("运行结束")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", self.exit_app)
        dialog.geometry("560x260")

        main = ttk.Frame(dialog, padding=18)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text=f"{PROJECT_NAME} 模拟已结束", font=("Microsoft YaHei", 14, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(
            main,
            text=f"部族汇总已保存到：{OUTPUT_XLSX_NAME}\n个体数据已保存到：{OUTPUT_CSV_NAME}",
            justify="left",
        ).pack(anchor="w", pady=(0, 18))

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="重新运行", command=lambda: self.rerun(dialog)).pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="返回", command=lambda: self.return_to_settings(dialog)).pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="退出", command=self.exit_app).pack(side="left")

    def rerun(self, dialog=None):
        if dialog is not None:
            dialog.destroy()
        settings = copy.deepcopy(self.settings)
        self.root.destroy()
        RuntimeWindow(settings).run()

    def return_to_settings(self, dialog=None):
        self.is_running = False
        try:
            save_outputs(self.env)
        except Exception:
            pass
        if dialog is not None:
            dialog.destroy()
        self.root.destroy()
        from gui_settings import StartConfigWindow
        StartConfigWindow().run()

    def exit_app(self):
        self.is_running = False
        try:
            save_outputs(self.env)
        except Exception:
            pass
        self.root.destroy()
        raise SystemExit

    def run(self):
        self.root.after(100, self.step)
        self.root.mainloop()
