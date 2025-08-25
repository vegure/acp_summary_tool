# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
import os
import sys
import webbrowser
from markdown2 import markdown
import main_func
from image_processor import ImageProcessor
import logging
import threading
import time
from PIL import Image, ImageTk
import shutil
import json
import datetime  # 添加导入以支持自动模式根据时间切换
# 导入LLM客户端注册中心
from llm_client import LLMClientRegistry
# 导入HTML渲染组件
from tkhtmlview import HTMLLabel


# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ACPReportGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("ACP 总结报告工具")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # 跟踪临时目录
        self.temp_dirs = []
        
        # 加载配置
        self.load_config()
        
        # 添加窗口关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 设置中文字体和现代扁平化样式
        self.style = ttk.Style()
        
        # 配置现代扁平化主题
        self.style.theme_use('clam')
        
        # 定义主题颜色方案
        self.themes = {
            'light': {
                'primary_color': '#FF6B9B',  # 糖果粉
                'secondary_color': '#7ED6DF',  # 糖果蓝
                'accent_color': '#F9D423',  # 糖果黄
                'background_color': '#F5F5F5',  # 浅灰背景（带透明度效果）
                'card_color': '#FFFFFF',  # 卡片白色
                'text_color': '#333333',  # 深灰文字
                'text_light': '#666666',  # 浅灰文字
                'border_color': '#E0E0E0'  # 边框颜色
            },
            'dark': {
                'primary_color': '#FF6B9B',  # 糖果粉
                'secondary_color': '#7ED6DF',  # 糖果蓝
                'accent_color': '#F9D423',  # 糖果黄
                'background_color': '#2D2D2D',  # 深灰背景
                'card_color': '#3A3A3A',  # 卡片深灰
                'text_color': '#F5F5F5',  # 浅灰文字
                'text_light': '#CCCCCC',  # 更浅灰文字
                'border_color': '#4A4A4A'  # 边框颜色
            }
        }
        
        # 获取当前主题（从配置或自动检测）
        self.theme_mode = self.config.get('theme_mode', 'auto')
        self.current_theme = self.get_theme()
        
        # 应用主题
        self.apply_theme()

        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建左侧控制面板
        self.control_frame = ttk.LabelFrame(self.main_frame, text="控制面板", padding="15")
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15), pady=(0, 5))
        self.control_frame.configure(width=250)
        # 确保宽度固定，不受内容影响
        self.control_frame.pack_propagate(False)
        
        # 选择文件夹按钮
        self.select_folder_btn = ttk.Button(
            self.control_frame, 
            text="选择图片文件夹", 
            command=self.select_folder,
            style="Primary.TButton"
        )
        self.select_folder_btn.pack(fill=tk.X, pady=(0, 12))
        
        # 选择单个图片按钮
        self.select_file_btn = ttk.Button(
            self.control_frame, 
            text="选择单个图片", 
            command=self.select_file,
            style="Primary.TButton"
        )
        self.select_file_btn.pack(fill=tk.X, pady=(0, 12))
        
        # 处理按钮
        self.process_btn = ttk.Button(
            self.control_frame, 
            text="生成总结报告", 
            command=self.start_processing,
            state=tk.DISABLED,
            style="Success.TButton"
        )
        self.process_btn.pack(fill=tk.X, pady=(0, 12))
        
        # 添加分隔线
        ttk.Separator(self.control_frame).pack(fill=tk.X, pady=12)
        
        # 保存按钮
        self.save_btn = ttk.Button(
            self.control_frame, 
            text="保存报告", 
            command=self.save_report,
            state=tk.DISABLED,
            style="Primary.TButton"
        )
        self.save_btn.pack(fill=tk.X, pady=(0, 12))
        
        # 打开浏览器按钮
        self.browser_btn = ttk.Button(
            self.control_frame, 
            text="在浏览器中查看", 
            command=self.open_in_browser,
            state=tk.DISABLED,
            style="Primary.TButton"
        )
        self.browser_btn.pack(fill=tk.X, pady=(0, 12))

        # 配置按钮
        self.config_btn = ttk.Button(
            self.control_frame, 
            text="配置", 
            command=self.open_config_dialog,
            style="TButton"
        )
        self.config_btn.pack(fill=tk.X, pady=(0, 12))
        
        # 添加分隔线
        ttk.Separator(self.control_frame).pack(fill=tk.X, pady=12)
        
        # 创建进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.control_frame,
            variable=self.progress_var,
            mode="determinate"
        )
        self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))
        
        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("等待选择图片...")
        self.status_label = ttk.Label(
            self.control_frame, 
            textvariable=self.status_var, 
            relief=tk.FLAT, 
            anchor=tk.W,
            padding=5
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        
        # 创建右侧reported区域
        self.report_frame = ttk.LabelFrame(self.main_frame, text="总结报告", padding="15")
        self.report_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # 创建标签页控件
        self.tab_control = ttk.Notebook(self.report_frame, style="TNotebook")
        self.style.configure("TNotebook", tabposition='n', padding=5)
        self.style.configure("TNotebook.Tab", font=('SimHei', 10), padding=[15, 5], background=self.card_color)
        
        # 创建原始报告标签页
        self.raw_report_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.raw_report_tab, text="Markdown 报告")
        
        # 创建渲染后的报告标签页
        self.rendered_report_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.rendered_report_tab, text="渲染报告")
        
        self.tab_control.pack(fill=tk.BOTH, expand=True)
        
        # 在原始报告标签页中添加文本框
        self.report_text = scrolledtext.ScrolledText(
                self.raw_report_tab, 
                wrap=tk.WORD,
                font=('PingFang SC', 10),
                bg=self.card_color,
                borderwidth=1,
                relief='solid'
            )
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 在渲染报告标签页中添加占位标签
        self.html_label = ttk.Label(self.rendered_report_tab, text="报告将在这里渲染", background=self.card_color)
        self.html_label.pack(fill=tk.BOTH, expand=True)
        
        # 初始化变量
        self.selected_paths = []
        self.report_content = ""
        self.html_content = ""
        # 加载配置
        self.load_config()
        
    def select_folder(self):
        """选择图片文件夹"""
        folder_path = filedialog.askdirectory(title="选择图片文件夹")
        if folder_path:
            self.selected_paths = [folder_path]
            self.status_var.set(f"已选择文件夹: {os.path.basename(folder_path)}")
            self.process_btn.config(state=tk.NORMAL)
    
    def select_file(self):
        """选择单个图片文件"""
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[
                ("图片文件", "*.jpeg *.jpg *.png *.heic"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.selected_paths = [file_path]
            self.status_var.set(f"选择文件: {os.path.basename(file_path)}")
            self.process_btn.config(state=tk.NORMAL)
    
    def start_processing(self):
        """开始处理图片并生成报告"""
        if not self.selected_paths:
            self.status_var.set("请先选择图片文件夹或文件")
            return
        
        # 禁用按钮
        self.process_btn.config(state=tk.DISABLED)
        self.select_folder_btn.config(state=tk.DISABLED)
        self.select_file_btn.config(state=tk.DISABLED)
        self.status_var.set("正在处理图片...")
        self.progress_var.set(0)
        
        # 在新线程中处理
        threading.Thread(target=self.process_images).start()
    
    def process_images(self):
        """处理图片并生成报告"""
        try:
            # 禁用按钮
            self.process_btn.config(state=tk.DISABLED)
            self.select_folder_btn.config(state=tk.DISABLED)
            self.select_file_btn.config(state=tk.DISABLED)
            self.progress_var.set(0)

            # 创建临时目录
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="acp_temp_")
            # 跟踪临时目录
            self.temp_dirs.append(temp_dir)
            self.status_var.set(f"创建临时目录: {temp_dir}")

            # 检查路径类型并处理
            if os.path.isdir(self.selected_paths[0]):
                # 处理文件夹: 复制整个目录到临时目录
                folder_path = self.selected_paths[0]
                dest_path = os.path.join(temp_dir, os.path.basename(folder_path))
                shutil.copytree(folder_path, dest_path)
                self.status_var.set(f"已复制目录到临时位置: {dest_path}")
            else:
                # 处理单个文件: 创建目录并复制文件
                file_path = self.selected_paths[0]
                dest_dir = os.path.join(temp_dir, "single_file")
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy(file_path, dest_dir)
                self.status_var.set(f"已复制文件到临时位置: {dest_dir}")

            # 更新进度
            self.progress_var.set(20)

            # 使用图像处理器处理图片
            self.status_var.set("正在处理图片...")
            image_processor = ImageProcessor()

            # 处理所有非JPEG文件
            processed_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 处理图片
                    processed_file = image_processor.process_image(file_path, root)
                    if processed_file:
                        processed_files.append(processed_file)

            self.status_var.set(f"已处理 {len(processed_files)} 张图片")
            self.progress_var.set(50)

            # 按照文件创建时间从远到近排序图片
            self.status_var.set("正在排序图片...")
            # 定义按创建时间排序的函数
            def sort_by_creation_time(file_path):
                return os.path.getctime(file_path)
            
            # 排序图片
            sorted_images = sorted(processed_files, key=sort_by_creation_time)
            self.status_var.set(f"已排序 {len(sorted_images)} 张图片")
            self.progress_var.set(70)

            # 调用主函数处理
            self.status_var.set("正在生成总结报告...")
            main_func.main(images=sorted_images)

            # 读取生成的总结报告
            # 查找最新生成的final_summary_custom_*报告文件
            report_files = [f for f in os.listdir('.') if f.startswith('final_summary_custom_') and f.endswith('.md')]
            if report_files:
                report_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                report_file = report_files[0]
                with open(report_file, 'r', encoding='utf-8') as f:
                    self.report_content = f.read()
                self.status_var.set(f"已读取报告文件: {report_file}")
            else:
                # 尝试查找其他可能的报告文件
                other_report_files = [f for f in os.listdir('.') if f.startswith('final_summary_') and f.endswith('.md')]
                if other_report_files:
                    other_report_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    report_file = other_report_files[0]
                    with open(report_file, 'r', encoding='utf-8') as f:
                        self.report_content = f.read()
                    self.status_var.set(f"已读取备用报告文件: {report_file}")
                else:
                    self.status_var.set("错误: 未找到生成的报告文件")
                    return

            # 更新UI
            self.root.after(0, self.update_report_display)
            
            # 更新状态
            self.status_var.set("报告生成完成")
            self.progress_var.set(100)
            
            # 启用按钮
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_folder_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_file_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.browser_btn.config(state=tk.NORMAL))
            
        except Exception as e:
            logging.error(f"处理图片时出错: {str(e)}")
            self.status_var.set(f"处理出错: {str(e)}")
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_folder_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_file_btn.config(state=tk.NORMAL))
        finally:
            # 清理当前临时目录
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                # 从跟踪列表中移除
                if temp_dir in self.temp_dirs:
                    self.temp_dirs.remove(temp_dir)
    
    def update_report_display(self):
        """更新报告显示"""
        # 更新Markdown文本框
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, self.report_content)
        
        # 生成HTML内容
        try:
            # 确保使用markdown2模块的正确方法
            self.html_content = markdown(self.report_content, extras=['fenced-code-blocks', 'tables', 'header-ids'])
            logging.debug(f"Markdown转换成功，HTML长度: {len(self.html_content)}")
        except Exception as e:
            logging.error(f"Markdown转换失败: {str(e)}")
            self.html_content = f"<p>Markdown转换失败: {str(e)}</p>"
            # 显示错误消息
            messagebox.showerror("错误", f"Markdown转换失败: {str(e)}")
        
        # 保存HTML到临时文件
        temp_html = "temp_report.html"
        try:
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>ACP 总结报告</title>
                    <style>
                        body {{ font-family: 'PingFang SC', 'San Francisco', sans-serif; margin: 20px; line-height: 1.6; }}
                        h1, h2, h3 {{ color: #333; }}
                        p {{ margin-bottom: 10px; }}
                        ul, ol {{ margin-bottom: 10px; margin-left: 20px; }}
                        code {{ background-color: #f5f5f5; padding: 2px 4px; border-radius: 4px; }}
                        pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }}
                        table {{ border-collapse: collapse; width: 100%; margin-bottom: 10px; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                        th {{ background-color: #f2f2f2; }}
                    </style>
                </head>
                <body>
                    {self.html_content}
                </body>
                </html>
                """)
            logging.debug(f"HTML文件已保存到: {temp_html}")
        except Exception as e:
            logging.error(f"保存HTML文件失败: {str(e)}")
            messagebox.showerror("错误", f"保存HTML文件失败: {str(e)}")
        
        # 更新渲染报告标签页
        # 先清空现有内容
        for widget in self.rendered_report_tab.winfo_children():
            widget.destroy()
        
        # 创建一个按钮，用于在浏览器中打开
        browser_btn = ttk.Button(
            self.rendered_report_tab, 
            text="在浏览器中查看渲染报告", 
            command=self.open_in_browser,
            style="Primary.TButton"
        )
        browser_btn.pack(pady=15)
        
        # 添加HTML渲染组件
        html_label = HTMLLabel(
                self.rendered_report_tab, 
                html=self.html_content,
                bg=self.card_color,
                borderwidth=1,
                relief='solid'
            )
        html_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        html_label.fit_height()
        
        # 提示用户可以在浏览器中查看完整渲染效果
        tip_label = ttk.Label(
            self.rendered_report_tab, 
            text="提示: 您正在查看本地渲染的报告，点击按钮可在浏览器中查看完整效果",
            foreground=self.primary_color,
            background=self.card_color
        )
        tip_label.pack(pady=10)
        
        # 显示转换成功的消息
        self.status_var.set("Markdown报告已转换为HTML，点击'在浏览器中查看'按钮查看完整渲染效果")
    
    def save_report(self):
        """保存报告"""
        if not self.report_content:
            self.status_var.set("没有可保存的报告内容")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[
                ("Markdown文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ],
            title="保存报告"
        )
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.report_content)
            self.status_var.set(f"报告已保存至: {save_path}")
    
    def open_in_browser(self):
        """在浏览器中打开报告"""
        if not self.html_content:
            self.status_var.set("没有可显示的报告内容")
            return
        
        # 创建临时HTML文件
        temp_html = "temp_report.html"
        webbrowser.open('file://' + os.path.realpath(temp_html))
        self.status_var.set("已在浏览器中打开报告")

    def open_config_dialog(self):
        """打开配置对话框"""
        ConfigDialog(self.root, self)

    def load_config(self):
        """加载配置"""
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                logging.error(f"加载配置失败: {str(e)}")
                self.config = {}
        else:
            self.config = {}

    def save_config(self, config):
        """保存配置"""
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.config = config
            return True
        except Exception as e:
            logging.error(f"保存配置失败: {str(e)}")
            return False

    def test_api_connection(self, api_type, api_key):
        """测试API连接"""
        try:
            # API类型到客户端类型的映射
            api_type_map = {
                "火山引擎": "ark",
                "硅基流动": "silicon_flow",
                "本地大模型": "local_llm"
            }
            
            # 检查API类型是否支持
            if api_type not in api_type_map:
                return False, f"不支持的API类型: {api_type}"
            
            # 获取客户端类型
            client_type = api_type_map[api_type]
            
            # 构建配置参数
            config = None
            if client_type == "local_llm":
                # 对于本地大模型，需要从配置中获取地址、端口和模型名
                local_llm_config = self.config.get("local_llm", {})
                
                # 构建完整配置，包含LLM和VLM参数
                config = {
                    "llm_address": local_llm_config.get("llm_address", "localhost"),
                    "llm_port": local_llm_config.get("llm_port", "8000"),
                    "llm_model_name": local_llm_config.get("llm_model_name", "gpt-4o"),
                    "vlm_address": local_llm_config.get("vlm_address", "localhost"),
                    "vlm_port": local_llm_config.get("vlm_port", "8000"),
                    "vlm_model_name": local_llm_config.get("vlm_model_name", "gpt-4o")
                }
            
            # 使用工厂类获取客户端实例
            client = LLMClientRegistry.get_client(client_type, api_key, config)
            
            # 使用客户端自带的测试方法
            success, message = client.test_connection()
            return success, message
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 清理所有临时目录
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        # 关闭窗口
        self.root.destroy()

    def get_theme(self):
        # 根据模式获取当前主题
        if self.theme_mode == 'auto':
            # 自动模式: 6:00-18:00 使用亮色主题，其余时间使用暗色主题
            hour = datetime.datetime.now().hour
            return 'light' if 6 <= hour < 18 else 'dark'
        else:
            # 手动模式: 直接使用设置的主题
            return self.theme_mode

    def apply_theme(self):
        # 应用当前主题
        # 获取当前主题的颜色配置
        theme_colors = self.themes[self.current_theme]
        
        # 存储颜色变量
        self.primary_color = theme_colors['primary_color']
        self.secondary_color = theme_colors['secondary_color']
        self.accent_color = theme_colors['accent_color']
        self.background_color = theme_colors['background_color']
        self.card_color = theme_colors['card_color']
        self.text_color = theme_colors['text_color']
        self.text_light = theme_colors['text_light']
        self.border_color = theme_colors['border_color']
        
        # 配置样式 - 设置中文字体为苹方
        self.style.configure("TLabel", font=('PingFang SC', 12), foreground=self.text_color, background=self.background_color)
        self.style.configure("Header.TLabel", font=('PingFang SC', 14, 'bold'), foreground=self.text_color, background=self.background_color)
        self.style.configure("TButton", font=('PingFang SC', 12), padding=6)
        self.style.configure("Primary.TButton", foreground='white', background=self.primary_color)
        self.style.configure("Success.TButton", foreground='white', background=self.secondary_color)
        self.style.configure("Danger.TButton", foreground='white', background=self.accent_color)
        self.style.configure("TFrame", background=self.background_color)
        self.style.configure("TLabelFrame", background=self.background_color, borderwidth=1, relief='solid', padding=10)
        self.style.configure("TRadiobutton", background=self.background_color, foreground=self.text_color)
        self.style.configure("TProgressbar", thickness=8)
        
        # 重新配置根窗口背景
        self.root.configure(bg=self.background_color)
        
        # 如果主框架已存在，更新其背景色
        if hasattr(self, 'main_frame'):
            self.main_frame.configure(style="TFrame")
            # 更新所有子组件
            for child in self.root.winfo_children():
                self.update_widget_style(child)

    def update_widget_style(self, widget):
        # 递归更新组件样式
        # 更新当前组件
        if hasattr(widget, 'configure'):
            try:
                # 更新背景色
                if 'background' in widget.configure():
                    widget.configure(background=self.background_color)
                # 更新前景色
                if 'foreground' in widget.configure():
                    widget.configure(foreground=self.text_color)
                # 更新样式
                if hasattr(widget, 'config') and 'style' in widget.config():
                    widget_style = widget.cget('style')
                    if widget_style and not widget_style.startswith('T'):
                        widget.configure(style=widget_style)
            except tk.TclError:
                pass
        
        # 递归更新子组件
        for child in widget.winfo_children():
            self.update_widget_style(child)

    def toggle_theme(self, mode=None):
        # 切换主题模式
        if mode:
            self.theme_mode = mode
        else:
            # 循环切换模式: auto -> light -> dark -> auto
            modes = ['auto', 'light', 'dark']
            current_index = modes.index(self.theme_mode)
            self.theme_mode = modes[(current_index + 1) % len(modes)]
        
        # 更新当前主题
        self.current_theme = self.get_theme()
        
        # 保存配置
        self.config['theme_mode'] = self.theme_mode
        self.save_config(self.config)
        
        # 应用新主题
        self.apply_theme()


class ConfigDialog(tk.Toplevel):
    """API配置对话框"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.parent = parent
        self.app = app
        self.title("API配置")
        
        # 设置适当的初始大小，但允许调整
        self.geometry("500x550")
        self.resizable(True, True)
        
        # 使对话框模态
        self.grab_set()
        
        # 设置背景色
        self.configure(bg=self.app.background_color)
        
        # 创建主框架，使用pack布局让它填满整个窗口
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 设置列权重，使第二列能够扩展
        main_frame.columnconfigure(1, weight=1)
        
        # API类型选择
        row = 0
        ttk.Label(main_frame, text="API类型:", font=('PingFang SC', 12)).grid(row=row, column=0, sticky=tk.W, pady=(0, 12))
        self.api_type = tk.StringVar(value="火山引擎")
        api_type_frame = ttk.Frame(main_frame)
        api_type_frame.grid(row=row, column=1, sticky=tk.W, pady=(0, 12))
        
        ttk.Radiobutton(
            api_type_frame, 
            text="火山引擎", 
            variable=self.api_type, 
            value="火山引擎"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Radiobutton(
            api_type_frame, 
            text="硅基流动", 
            variable=self.api_type, 
            value="硅基流动"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Radiobutton(
            api_type_frame, 
            text="本地大模型", 
            variable=self.api_type, 
            value="本地大模型"
        ).pack(side=tk.LEFT)
        
        # 绑定API类型变更事件
        self.api_type.trace_add("write", self.on_api_type_changed)
        
        # 火山引擎模型配置区域
        row += 1
        self.volcano_engine_frame = ttk.LabelFrame(main_frame, text="火山引擎模型配置")
        self.volcano_engine_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(10, 12))
        
        # 火山引擎列权重设置
        self.volcano_engine_frame.columnconfigure(1, weight=1)
        
        # 火山引擎模型类型选择
        ttk.Label(self.volcano_engine_frame, text="模型类型:", font=('PingFang SC', 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.volcano_engine_model_type = tk.StringVar(value="LLM")
        volcano_model_type_frame = ttk.Frame(self.volcano_engine_frame)
        volcano_model_type_frame.grid(row=0, column=1, sticky=tk.W, pady=(0, 8), padx=(0, 10))
        
        ttk.Radiobutton(
            volcano_model_type_frame, 
            text="文本模型 (LLM)", 
            variable=self.volcano_engine_model_type, 
            value="LLM"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Radiobutton(
            volcano_model_type_frame, 
            text="多模态模型 (VLM)", 
            variable=self.volcano_engine_model_type, 
            value="VLM"
        ).pack(side=tk.LEFT)
        
        # 火山引擎模型选择
        ttk.Label(self.volcano_engine_frame, text="选择模型:", font=('PingFang SC', 10)).grid(row=1, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.volcano_engine_model = tk.StringVar()
        
        # 火山引擎模型下拉菜单
        self.volcano_engine_model_menu = ttk.Combobox(self.volcano_engine_frame, textvariable=self.volcano_engine_model, width=25)
        
        # 内置火山引擎模型列表
        self.volcano_engine_llm_models = ["doubao-seed-1-6-thinking-250715", "deepseek-r1-250528", "kimi-k2-250711"]
        self.volcano_engine_vlm_models = ["doubao-1-5-thinking-vision-pro-250428", "doubao-1-5-ui-tars-250428"]
        
        # 默认显示LLM模型
        self.volcano_engine_model_menu['values'] = self.volcano_engine_llm_models
        
        # 将下拉菜单添加到界面
        self.volcano_engine_model_menu.grid(row=1, column=1, sticky=tk.W+tk.E, pady=(0, 8), padx=(0, 10))
        
        # 绑定火山引擎模型类型变更事件
        self.volcano_engine_model_type.trace_add("write", self.on_volcano_engine_model_type_changed)
        
        # 硅基流程模型配置区域
        row += 1
        self.deepseek_frame = ttk.LabelFrame(main_frame, text="硅基流程模型配置")
        self.deepseek_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(10, 12))
        
        # DeepSeek列权重设置
        self.deepseek_frame.columnconfigure(1, weight=1)
        
        # DeepSeek模型类型选择
        ttk.Label(self.deepseek_frame, text="模型类型:", font=('PingFang SC', 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.deepseek_model_type = tk.StringVar(value="LLM")
        deepseek_model_type_frame = ttk.Frame(self.deepseek_frame)
        deepseek_model_type_frame.grid(row=0, column=1, sticky=tk.W, pady=(0, 8), padx=(0, 10))
        
        ttk.Radiobutton(
            deepseek_model_type_frame, 
            text="文本模型 (LLM)", 
            variable=self.deepseek_model_type, 
            value="LLM"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Radiobutton(
            deepseek_model_type_frame, 
            text="多模态模型 (VLM)", 
            variable=self.deepseek_model_type, 
            value="VLM"
        ).pack(side=tk.LEFT)
        
        # DeepSeek模型选择
        ttk.Label(self.deepseek_frame, text="选择模型:", font=('PingFang SC', 10)).grid(row=1, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.deepseek_model = tk.StringVar()
        
        # DeepSeek模型下拉菜单
        self.deepseek_model_menu = ttk.Combobox(self.deepseek_frame, textvariable=self.deepseek_model, width=25)
        
        # 内置DeepSeek模型列表
        self.deepseek_llm_models = ["deepseek-chat", "deepseek-coder", "deepseek-r1"]
        self.deepseek_vlm_models = ["deepseek-vl"]
        
        # 默认显示LLM模型
        self.deepseek_model_menu['values'] = self.deepseek_llm_models
        
        # 将下拉菜单添加到界面
        self.deepseek_model_menu.grid(row=1, column=1, sticky=tk.W+tk.E, pady=(0, 8), padx=(0, 10))
        
        # 绑定DeepSeek模型类型变更事件
        self.deepseek_model_type.trace_add("write", self.on_deepseek_model_type_changed)
        
        # 本地大模型配置区域
        row += 1
        self.local_llm_frame = ttk.LabelFrame(main_frame, text="本地大模型配置")
        self.local_llm_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(10, 12))
        
        # 本地大模型类型选择
        ttk.Label(self.local_llm_frame, text="任务类型:", font=('PingFang SC', 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.local_llm_task_type = tk.StringVar(value="LLM")
        local_llm_task_frame = ttk.Frame(self.local_llm_frame)
        local_llm_task_frame.grid(row=0, column=1, sticky=tk.W, pady=(0, 8), padx=(0, 10))
        
        ttk.Radiobutton(
            local_llm_task_frame, 
            text="文本模型 (LLM)", 
            variable=self.local_llm_task_type, 
            value="LLM"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Radiobutton(
            local_llm_task_frame, 
            text="多模态模型 (VLM)", 
            variable=self.local_llm_task_type, 
            value="VLM"
        ).pack(side=tk.LEFT)
        
        # 为本地大模型配置区域设置列权重
        self.local_llm_frame.columnconfigure(1, weight=1)
        
        # 绑定本地大模型任务类型变更事件
        self.local_llm_task_type.trace_add("write", self.on_local_llm_task_type_changed)
        
        # LLM 配置区域
        self.local_llm_llm_frame = ttk.Frame(self.local_llm_frame)
        self.local_llm_llm_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(5, 5))
        
        # LLM 地址
        ttk.Label(self.local_llm_llm_frame, text="LLM地址:", font=('PingFang SC', 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.local_llm_llm_address = ttk.Entry(self.local_llm_llm_frame, width=30)
        self.local_llm_llm_address.grid(row=0, column=1, sticky=tk.W+tk.E, pady=(0, 8), padx=(0, 10))
        
        # LLM 端口
        ttk.Label(self.local_llm_llm_frame, text="LLM端口:", font=('PingFang SC', 10)).grid(row=1, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.local_llm_llm_port = ttk.Entry(self.local_llm_llm_frame, width=10)
        self.local_llm_llm_port.grid(row=1, column=1, sticky=tk.W, pady=(0, 8), padx=(0, 10))
        
        # LLM 模型名
        ttk.Label(self.local_llm_llm_frame, text="LLM模型名:", font=('PingFang SC', 10)).grid(row=2, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.local_llm_llm_model = ttk.Entry(self.local_llm_llm_frame, width=30)
        self.local_llm_llm_model.grid(row=2, column=1, sticky=tk.W+tk.E, pady=(0, 8), padx=(0, 10))
        
        # VLM 配置区域
        self.local_llm_vlm_frame = ttk.Frame(self.local_llm_frame)
        self.local_llm_vlm_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(5, 5))
        
        # VLM 地址
        ttk.Label(self.local_llm_vlm_frame, text="VLM地址:", font=('PingFang SC', 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.local_llm_vlm_address = ttk.Entry(self.local_llm_vlm_frame, width=30)
        self.local_llm_vlm_address.grid(row=0, column=1, sticky=tk.W+tk.E, pady=(0, 8), padx=(0, 10))
        
        # VLM 端口
        ttk.Label(self.local_llm_vlm_frame, text="VLM端口:", font=('PingFang SC', 10)).grid(row=1, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.local_llm_vlm_port = ttk.Entry(self.local_llm_vlm_frame, width=10)
        self.local_llm_vlm_port.grid(row=1, column=1, sticky=tk.W, pady=(0, 8), padx=(0, 10))
        
        # VLM 模型名
        ttk.Label(self.local_llm_vlm_frame, text="VLM模型名:", font=('PingFang SC', 10)).grid(row=2, column=0, sticky=tk.W, pady=(0, 8), padx=(10, 0))
        self.local_llm_vlm_model = ttk.Entry(self.local_llm_vlm_frame, width=30)
        self.local_llm_vlm_model.grid(row=2, column=1, sticky=tk.W+tk.E, pady=(0, 8), padx=(0, 10))
        
        # API密钥输入
        row += 1
        ttk.Label(main_frame, text="API密钥:", font=('PingFang SC', 12)).grid(row=row, column=0, sticky=tk.W, pady=(0, 12))
        self.api_key_entry = ttk.Entry(main_frame, width=30, show="*")
        self.api_key_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=(0, 12))
        self.api_key_label = ttk.Label(main_frame, text="(本地大模型可选)", font=('PingFang SC', 9))
        self.api_key_label.grid(row=row, column=2, sticky=tk.W, pady=(0, 12))
        
        # 校验按钮
        row += 1
        self.test_btn = ttk.Button(
            main_frame, 
            text="校验连接", 
            command=self.test_connection
        )
        self.test_btn.grid(row=row, column=0, columnspan=2, pady=(0, 12))
        
        # 状态标签
        row += 1
        self.status_var = tk.StringVar()
        self.status_var.set("请输入API密钥并校验连接")
        self.status_label = ttk.Label(
            main_frame, 
            textvariable=self.status_var, 
            anchor=tk.W,
            padding=5
        )
        self.status_label.grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(0, 12))
        
        # 主题设置
        row += 1
        ttk.Label(main_frame, text="主题模式:", font=('PingFang SC', 12)).grid(row=row, column=0, sticky=tk.W, pady=(15, 12))
        self.theme_mode = tk.StringVar(value=self.app.theme_mode)
        theme_frame = ttk.Frame(main_frame)
        theme_frame.grid(row=row, column=1, sticky=tk.W, pady=(15, 12))
        
        ttk.Radiobutton(
            theme_frame, 
            text="自动", 
            variable=self.theme_mode, 
            value="auto"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Radiobutton(
            theme_frame, 
            text="白天", 
            variable=self.theme_mode, 
            value="light"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Radiobutton(
            theme_frame, 
            text="黑夜", 
            variable=self.theme_mode, 
            value="dark"
        ).pack(side=tk.LEFT)
        
        # 添加一个间隔行，确保按钮在底部
        row += 1
        ttk.Frame(main_frame, height=20).grid(row=row, column=0)
        
        # 确保按钮在底部显示
        row += 1
        # 创建一个框架来放置底部按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(10, 0), sticky=tk.E)
        
        # 保存按钮
        self.save_btn = ttk.Button(
            btn_frame, 
            text="保存配置", 
            command=self.save_dialog_config
        )
        self.save_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        # 取消按钮
        self.cancel_btn = ttk.Button(
            btn_frame, 
            text="取消", 
            command=self.destroy
        )
        self.cancel_btn.pack(side=tk.LEFT)
        
        # 加载现有配置
        self.load_existing_config()
        
        # 初始显示状态
        self.on_api_type_changed()
        self.on_local_llm_task_type_changed()
        
        # 添加窗口大小变化事件，动态调整布局
        self.bind('<Configure>', self.on_resize)
        
    def on_resize(self, event):
        """窗口大小变化时的回调，确保元素不会重叠"""
        # 这里可以实现更复杂的碰撞检测逻辑
        # 简单的实现是确保所有元素都在正确的行上
        self.update_idletasks()
    
    def on_api_type_changed(self, *args):
        """当API类型变更时，显示或隐藏相应的配置区域"""
        api_type = self.api_type.get()
        
        # 首先隐藏所有特定API配置区域
        self.volcano_engine_frame.grid_remove()
        self.deepseek_frame.grid_remove()
        self.local_llm_frame.grid_remove()
        
        # 然后根据选择的API类型显示相应的配置区域
        if api_type == "火山引擎":
            self.volcano_engine_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(10, 12))
            self.api_key_label.config(text="")
        elif api_type == "硅基流动":
            self.deepseek_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(10, 12))
            self.api_key_label.config(text="")
        elif api_type == "本地大模型":
            self.local_llm_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(10, 12))
            self.api_key_label.config(text="(可选)")
            
        # 触发窗口重绘以适应布局变化
        self.update_idletasks()
        
    def on_volcano_engine_model_type_changed(self, *args):
        """当火山引擎模型类型变更时，更新模型下拉菜单"""
        model_type = self.volcano_engine_model_type.get()
        current_model = self.volcano_engine_model.get()
        
        # 根据选择的模型类型更新下拉菜单选项
        if model_type == "LLM":
            self.volcano_engine_model_menu['values'] = self.volcano_engine_llm_models
            # 如果当前选择的模型在新列表中，保持选择，否则选择第一个
            if current_model in self.volcano_engine_llm_models:
                self.volcano_engine_model.set(current_model)
            elif self.volcano_engine_llm_models:
                self.volcano_engine_model.set(self.volcano_engine_llm_models[0])
        else:
            self.volcano_engine_model_menu['values'] = self.volcano_engine_vlm_models
            # 如果当前选择的模型在新列表中，保持选择，否则选择第一个
            if current_model in self.volcano_engine_vlm_models:
                self.volcano_engine_model.set(current_model)
            elif self.volcano_engine_vlm_models:
                self.volcano_engine_model.set(self.volcano_engine_vlm_models[0])
        
    def on_deepseek_model_type_changed(self, *args):
        """当DeepSeek模型类型变更时，更新模型下拉菜单"""
        model_type = self.deepseek_model_type.get()
        current_model = self.deepseek_model.get()
        
        # 根据选择的模型类型更新下拉菜单选项
        if model_type == "LLM":
            self.deepseek_model_menu['values'] = self.deepseek_llm_models
            # 如果当前选择的模型在新列表中，保持选择，否则选择第一个
            if current_model in self.deepseek_llm_models:
                self.deepseek_model.set(current_model)
            elif self.deepseek_llm_models:
                self.deepseek_model.set(self.deepseek_llm_models[0])
        else:
            self.deepseek_model_menu['values'] = self.deepseek_vlm_models
            # 如果当前选择的模型在新列表中，保持选择，否则选择第一个
            if current_model in self.deepseek_vlm_models:
                self.deepseek_model.set(current_model)
            elif self.deepseek_vlm_models:
                self.deepseek_model.set(self.deepseek_vlm_models[0])
                
    def on_local_llm_task_type_changed(self, *args):
        """当本地大模型任务类型变更时，显示或隐藏相应的配置区域"""
        task_type = self.local_llm_task_type.get()
        
        # 根据选择的任务类型显示或隐藏配置区域
        if task_type == "LLM":
            self.local_llm_llm_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(5, 5))
            self.local_llm_vlm_frame.grid_remove()
        else:
            self.local_llm_llm_frame.grid_remove()
            self.local_llm_vlm_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(5, 5))
    
    def test_connection(self):
        """测试API连接"""
        api_type = self.api_type.get()
        api_key = self.api_key_entry.get()
        
        if not api_key:
            self.status_var.set("请输入API密钥")
            return
        
        self.status_var.set("正在测试连接...")
        success, message = self.app.test_api_connection(api_type, api_key)
        
        if success:
            self.status_var.set(f"连接成功: {message}")
        else:
            self.status_var.set(f"连接失败: {message}")

    def load_existing_config(self):
        """加载现有配置"""
        api_type = self.app.config.get("api_type", "火山引擎")
        self.api_type.set(api_type)
        
        api_key = self.app.config.get("api_keys", {}).get(api_type, "")
        self.api_key_entry.insert(0, api_key)
        
        # 加载火山引擎配置
        volcano_engine_config = self.app.config.get("volcano_engine", {})
        self.volcano_engine_model_type.set(volcano_engine_config.get("model_type", "LLM"))
        
        # 触发模型类型变更事件以更新下拉菜单
        self.on_volcano_engine_model_type_changed()
        
        # 设置模型选择
        if volcano_engine_config.get("model"):
            self.volcano_engine_model.set(volcano_engine_config.get("model"))
        elif self.volcano_engine_llm_models:
            self.volcano_engine_model.set(self.volcano_engine_llm_models[0])
        
        # 加载DeepSeek配置
        deepseek_config = self.app.config.get("deepseek", {})
        self.deepseek_model_type.set(deepseek_config.get("model_type", "LLM"))
        
        # 触发模型类型变更事件以更新下拉菜单
        self.on_deepseek_model_type_changed()
        
        # 设置模型选择
        if deepseek_config.get("model"):
            self.deepseek_model.set(deepseek_config.get("model"))
        elif self.deepseek_llm_models:
            self.deepseek_model.set(self.deepseek_llm_models[0])
        
        # 加载本地大模型配置
        local_llm_config = self.app.config.get("local_llm", {})
        
        # 加载LLM配置
        self.local_llm_llm_address.insert(0, local_llm_config.get("llm_address", "localhost"))
        self.local_llm_llm_port.insert(0, local_llm_config.get("llm_port", "8000"))
        self.local_llm_llm_model.insert(0, local_llm_config.get("llm_model_name", "gpt-4o"))
        
        # 加载VLM配置
        self.local_llm_vlm_address.insert(0, local_llm_config.get("vlm_address", "localhost"))
        self.local_llm_vlm_port.insert(0, local_llm_config.get("vlm_port", "8000"))
        self.local_llm_vlm_model.insert(0, local_llm_config.get("vlm_model_name", "gpt-4o"))
        
        # 加载主题模式
        theme_mode = self.app.config.get("theme_mode", "auto")
        self.theme_mode.set(theme_mode)

    def save_dialog_config(self):
        """保存配置"""
        api_type = self.api_type.get()
        api_key = self.api_key_entry.get()
        theme_mode = self.theme_mode.get()
        
        # 对于非本地大模型，API密钥是必需的
        if api_type != "本地大模型" and not api_key:
            messagebox.showerror("错误", "请输入API密钥")
            return
        
        # 更新配置
        config = self.app.config.copy()
        config["api_type"] = api_type
        
        api_keys = config.get("api_keys", {})
        api_keys[api_type] = api_key
        config["api_keys"] = api_keys
        
        # 保存火山引擎配置
        volcano_engine_config = {
            "model_type": self.volcano_engine_model_type.get(),
            "model": self.volcano_engine_model.get()
        }
        config["volcano_engine"] = volcano_engine_config
        
        # 保存DeepSeek配置
        deepseek_config = {
            "model_type": self.deepseek_model_type.get(),
            "model": self.deepseek_model.get()
        }
        config["deepseek"] = deepseek_config
        
        # 保存本地大模型配置
        local_llm_config = {
            "llm_address": self.local_llm_llm_address.get().strip() or "localhost",
            "llm_port": self.local_llm_llm_port.get().strip() or "8000",
            "llm_model_name": self.local_llm_llm_model.get().strip() or "gpt-4o",
            "vlm_address": self.local_llm_vlm_address.get().strip() or "localhost",
            "vlm_port": self.local_llm_vlm_port.get().strip() or "8000",
            "vlm_model_name": self.local_llm_vlm_model.get().strip() or "gpt-4o"
        }
        config["local_llm"] = local_llm_config
        
        # 保存主题设置
        config["theme_mode"] = theme_mode
        
        # 保存配置
        if self.app.save_config(config):
            # 更新应用的主题
            self.app.theme_mode = theme_mode
            self.app.current_theme = self.app.get_theme()
            self.app.apply_theme()
            
            messagebox.showinfo("成功", "配置已保存")
            self.destroy()
        else:
            messagebox.showerror("错误", "保存配置失败")


# 主函数保持不变
def main():
    """主函数"""
    root = tk.Tk()
    app = ACPReportGenerator(root)
    root.mainloop()

if __name__ == "__main__":
    main()