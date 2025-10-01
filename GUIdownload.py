#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化的数据补充工具
基于GUI.py的删减版本，专门用于补充数据功能
"""

import sys
import os
import ctypes
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTextEdit, QPushButton, QFileDialog, QMessageBox, QProgressBar, 
                             QComboBox, QDateEdit, QGroupBox, QCheckBox, QGridLayout, QDesktopWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QMutex
from PyQt5.QtGui import QFont, QIcon
from khQTTools import supplement_history_data

# 自定义控件类，禁用滚轮事件
class NoWheelComboBox(QComboBox):
    """禁用滚轮事件的QComboBox"""
    def wheelEvent(self, event):
        event.ignore()

class NoWheelDateEdit(QDateEdit):
    """禁用滚轮事件的QDateEdit"""
    def wheelEvent(self, event):
        event.ignore()

# 图标路径
ICON_PATH = os.path.join(os.path.dirname(__file__), 'icons')

# 配置日志记录
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, 'supplement.log'),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s', 
    filemode='w'
)

# 同时将日志输出到控制台
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

class SupplementThread(QThread):
    """数据补充线程"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params
        self.running = True
        self.mutex = QMutex()
        self.supplement_stats = {
            'success_count': 0,
            'empty_data_count': 0,
            'error_count': 0,
            'empty_stocks': []
        }

    def run(self):
        try:
            if not self.isRunning():
                return
                
            # 参数验证
            if not self.params.get('stock_files'):
                raise ValueError("股票代码列表为空")

            def progress_callback(percent):
                if not self.isRunning():
                    raise InterruptedError("数据补充被中断")
                self.progress.emit(percent)
                    
            def log_callback(message):
                if not self.isRunning():
                    raise InterruptedError("用户中断")
                self.status_update.emit(message)

            def check_interrupt():
                return not self.isRunning()

            # 使用默认字段列表
            default_fields = ["open", "high", "low", "close", "volume", "amount"]
            
            supplement_history_data(
                stock_files=self.params['stock_files'],
                field_list=default_fields,
                period_type=self.params['period_type'],
                start_date=self.params['start_date'],
                end_date=self.params['end_date'],
                time_range='all',
                dividend_type='none',  # 固定不复权
                progress_callback=progress_callback,
                log_callback=log_callback,
                check_interrupt=check_interrupt
            )

            if self.isRunning():
                self.finished.emit(True, "数据补充完成！")
                
        except Exception as e:
            error_msg = f"补充数据过程中发生错误: {str(e)}"
            logging.error(error_msg, exc_info=True)
            if self.isRunning():
                self.error.emit(error_msg)
                self.finished.emit(False, error_msg)

    def stop(self):
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()
        
    def isRunning(self):
        self.mutex.lock()
        result = self.running
        self.mutex.unlock()
        return result

class SupplementDataTool(QMainWindow):
    """简化的数据补充工具"""
    
    def __init__(self):
        super().__init__()
        self.supplement_thread = None
        self.font_scale = 1.0
        self.detect_screen_resolution()
        self.init_ui()
        self.apply_styles()
        
    def detect_screen_resolution(self):
        """检测屏幕分辨率并设置缩放因子"""
        desktop = QDesktopWidget()
        screen_geometry = desktop.screenGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # 根据屏幕宽度确定字体缩放比例（与主界面保持一致）
        if screen_width >= 3840:  # 4K及以上分辨率
            self.font_scale = 1.8
        elif screen_width >= 2560:  # 2K分辨率
            self.font_scale = 1.4
        elif screen_width >= 1920:  # 1080P分辨率
            self.font_scale = 1.0
        else:  # 低分辨率
            self.font_scale = 0.8
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('数据补充工具')
        self.setGeometry(100, 100, 600, 650)
        
        # 设置Windows深色标题栏
        try:
            if sys.platform == 'win32':
                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                DWMWA_CAPTION_COLOR = 35
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                    ctypes.byref(ctypes.c_int(1)), 
                    ctypes.sizeof(ctypes.c_int)
                )
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_CAPTION_COLOR,
                    ctypes.byref(ctypes.c_int(0x2C2C2C)),
                    ctypes.sizeof(ctypes.c_int)
                )
        except Exception as e:
            logging.warning(f"设置Windows标题栏深色模式失败: {str(e)}")
        
        # 设置图标
        icon_path = os.path.join(ICON_PATH, 'stock_icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题字体
        title_font = QFont()
        title_font.setPointSize(int(10 * self.font_scale))
        title_font.setBold(True)
        
        # 添加各个组件
        self.add_stock_group(main_layout, title_font)
        self.add_period_group(main_layout, title_font)
        self.add_date_group(main_layout, title_font)
        self.add_supplement_section(main_layout)
        
        # 状态标签
        self.status_label = QLabel("准备就绪")
        main_layout.addWidget(self.status_label)
        
    def add_stock_group(self, layout, title_font):
        """添加股票代码列表组"""
        stocks_group = QGroupBox("股票代码列表文件")
        stocks_group.setFont(title_font)
        stock_layout = QVBoxLayout()
        
        # 股票类型复选框
        self.stock_checkboxes = {}
        stock_types = {
            'hs_a': '沪深A股',
            'gem': '创业板',
            'sci': '科创板',
            'zz500': '中证500成分股',
            'hs300': '沪深300成分股',
            'sz50': '上证50成分股',
            'indices': '常用指数',
            'convertible_bonds': '沪深转债',
            'custom': '自选清单'
        }
        
        # 创建3行3列的网格布局
        grid_layout = QGridLayout()
        row = 0
        col = 0
        
        for stock_type, display_name in stock_types.items():
            checkbox = QCheckBox(display_name)
            checkbox.stateChanged.connect(self.update_stock_files_preview)
            self.stock_checkboxes[stock_type] = checkbox
            grid_layout.addWidget(checkbox, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        stock_layout.addLayout(grid_layout)
        
        # 添加自定义文件按钮和清空按钮
        button_layout = QHBoxLayout()
        
        add_custom_button = QPushButton("添加自定义列表")
        add_custom_button.clicked.connect(self.add_custom_stock_file)
        button_layout.addWidget(add_custom_button)
        
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self.clear_stock_files)
        button_layout.addWidget(clear_button)
        
        stock_layout.addLayout(button_layout)
        
        # 预览区域
        self.stock_files_preview = QTextEdit()
        self.stock_files_preview.setMaximumHeight(100)
        self.stock_files_preview.setReadOnly(True)
        self.stock_files_preview.setText("未选择任何股票列表文件")
        stock_layout.addWidget(self.stock_files_preview)
        
        stocks_group.setLayout(stock_layout)
        layout.addWidget(stocks_group)

    def add_period_group(self, layout, title_font):
        """添加周期类型组"""
        period_group = QGroupBox("周期类型")
        period_group.setFont(title_font)
        period_layout = QHBoxLayout()

        self.period_type_combo = NoWheelComboBox()
        self.period_type_combo.addItems(['tick', '1m', '5m', '1d'])
        period_layout.addWidget(self.period_type_combo)
        period_group.setLayout(period_layout)
        layout.addWidget(period_group)

    def add_date_group(self, layout, title_font):
        """添加日期范围组"""
        date_group = QGroupBox("日期范围")
        date_group.setFont(title_font)
        date_layout = QHBoxLayout()
        
        start_date_layout = QHBoxLayout()
        start_date_layout.addWidget(QLabel("起始日期:"))
        self.start_date_edit = NoWheelDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate(2024, 1, 1))
        start_date_layout.addWidget(self.start_date_edit)
        
        end_date_layout = QHBoxLayout()
        end_date_layout.addWidget(QLabel("结束日期:"))
        self.end_date_edit = NoWheelDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        end_date_layout.addWidget(self.end_date_edit)
        
        date_layout.addLayout(start_date_layout)
        date_layout.addLayout(end_date_layout)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

    def add_supplement_section(self, layout):
        """添加补充数据按钮和进度条"""
        supplement_layout = QVBoxLayout()
        
        # 补充数据按钮
        self.supplement_button = QPushButton("补充数据")
        self.supplement_button.setMinimumHeight(40)
        self.supplement_button.clicked.connect(self.supplement_data)
        supplement_layout.addWidget(self.supplement_button)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(10)
        supplement_layout.addWidget(self.progress_bar)

        layout.addLayout(supplement_layout)

    def add_custom_stock_file(self):
        """添加自定义股票列表文件"""
        try:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "选择股票代码列表文件",
                data_dir,
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if files:
                current_files = []
                current_text = self.stock_files_preview.toPlainText().strip()
                if current_text and current_text != "未选择任何股票列表文件":
                    current_files = current_text.split('\n')
                
                for file in files:
                    if file not in current_files:
                        current_files.append(file)
                
                preview_text = "\n".join(current_files)
                self.stock_files_preview.setText(preview_text)
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"添加文件时出错: {str(e)}")

    def clear_stock_files(self):
        """清空股票列表预览"""
        try:
            for checkbox in self.stock_checkboxes.values():
                checkbox.setChecked(False)
            self.stock_files_preview.setText("未选择任何股票列表文件")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"清空列表时出错: {str(e)}")

    def update_stock_files_preview(self):
        """更新选中的股票文件预览"""
        try:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
            selected_files = []
            
            # 添加预定义列表文件
            for stock_type, checkbox in self.stock_checkboxes.items():
                if checkbox.isChecked():
                    filename = None
                    if stock_type == 'indices':
                        filename = os.path.join(data_dir, "指数_股票列表.csv")
                    elif stock_type == 'zz500':
                        filename = os.path.join(data_dir, "中证500成分股_股票列表.csv")
                    elif stock_type == 'hs300':
                        filename = os.path.join(data_dir, "沪深300成分股_股票列表.csv")
                    elif stock_type == 'sz50':
                        filename = os.path.join(data_dir, "上证50成分股_股票列表.csv")
                    elif stock_type == 'hs_a':
                        filename = os.path.join(data_dir, "沪深A股_股票列表.csv")
                    elif stock_type == 'gem':
                        filename = os.path.join(data_dir, "创业板_股票列表.csv")
                    elif stock_type == 'sci':
                        filename = os.path.join(data_dir, "科创板_股票列表.csv")
                    elif stock_type == 'convertible_bonds':
                        filename = os.path.join(data_dir, "沪深转债_列表.csv")
                    elif stock_type == 'custom':
                        filename = os.path.join(data_dir, "otheridx.csv")
                    
                    if filename and os.path.exists(filename):
                        selected_files.append(filename)
            
            if selected_files:
                self.stock_files_preview.setText('\n'.join(selected_files))
            else:
                self.stock_files_preview.setText("未选择任何股票列表文件")
                
        except Exception as e:
            logging.error(f"更新股票文件预览时出错: {str(e)}")

    def validate_date_range(self):
        """验证日期范围"""
        start_date = self.start_date_edit.date()
        end_date = self.end_date_edit.date()
        
        if end_date < start_date:
            QMessageBox.warning(self, "警告", "结束日期不能早于开始日期")
            return False
            
        return True

    def supplement_data(self):
        """补充数据按钮点击事件处理"""
        try:
            # 如果补充数据线程正在运行，点击按钮就停止补充
            if hasattr(self, 'supplement_thread') and self.supplement_thread and self.supplement_thread.isRunning():
                self.supplement_thread.stop()
                self.status_label.setText("补充数据已停止")
                self.reset_supplement_button()
                return
                
            # 验证日期范围
            if not self.validate_date_range():
                return
            
            # 获取选中的股票文件列表
            stock_files = []
            current_preview = self.stock_files_preview.toPlainText().strip()
            if current_preview and current_preview != "未选择任何股票列表文件":
                stock_files = current_preview.split('\n')
            
            if not stock_files:
                QMessageBox.warning(self, "警告", "请先选择股票列表文件！")
                return

            # 获取周期类型
            period_type = self.period_type_combo.currentText()

            # 获取日期范围
            start_date = self.start_date_edit.date().toString("yyyyMMdd")
            end_date = self.end_date_edit.date().toString("yyyyMMdd")

            # 更新按钮状态
            self.supplement_button.setText("停止补充")
            self.supplement_button.setEnabled(True)

            # 设置进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            # 记录开始时间
            self.status_label.setText("开始补充数据...")

            # 准备参数
            params = {
                'stock_files': stock_files,
                'period_type': period_type,
                'start_date': start_date,
                'end_date': end_date
            }

            # 启动补充线程
            self.supplement_thread = SupplementThread(params, self)
            self.supplement_thread.progress.connect(self.update_progress)
            self.supplement_thread.status_update.connect(self.update_status)
            self.supplement_thread.finished.connect(self.supplement_finished)
            self.supplement_thread.error.connect(self.handle_supplement_error)
            self.supplement_thread.start()

        except Exception as e:
            error_msg = f"启动补充数据时出错: {str(e)}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "错误", error_msg)
            self.reset_supplement_button()

    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)

    def update_status(self, message):
        """更新状态标签"""
        self.status_label.setText(message)

    def supplement_finished(self, success, message):
        """补充数据完成后的处理"""
        try:
            if success:
                self.status_label.setText("数据补充完成！")
                QMessageBox.information(self, "完成", message)
            else:
                self.status_label.setText("数据补充失败！")
                QMessageBox.warning(self, "失败", message)
        except Exception as e:
            logging.error(f"处理补充完成信号时出错: {str(e)}")
        finally:
            self.reset_supplement_button()

    def handle_supplement_error(self, error_msg):
        """处理补充数据错误"""
        try:
            self.status_label.setText("数据补充出错！")
            QMessageBox.critical(self, "错误", error_msg)
        except Exception as e:
            logging.error(f"处理补充错误信号时出错: {str(e)}")
        finally:
            self.reset_supplement_button()

    def reset_supplement_button(self):
        """重置补充按钮状态"""
        self.supplement_button.setText("补充数据")
        self.supplement_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
    def get_scaled_stylesheet(self):
        """获取根据分辨率缩放的样式表"""
        # 基础字体大小
        base_sizes = {
            'small': 12,
            'normal': 14, 
            'large': 16,
            'xl': 18,
            'xxl': 24,
            'xxxl': 30
        }
        
        # 计算缩放后的字体大小
        scaled_sizes = {k: int(v * self.font_scale) for k, v in base_sizes.items()}
        
        return f"""
            /* 主窗口和基础样式 */
            QMainWindow {{
                font-size: {scaled_sizes['normal']}px;
            }}
            
            QWidget#mainContainer {{
                background-color: #2b2b2b;
                color: #f0f0f0;
                border: none;
                font-size: {scaled_sizes['normal']}px;
            }}
            
            QWidget {{
                background-color: #2b2b2b;
                color: #f0f0f0;
                border: none;
                font-size: {scaled_sizes['normal']}px;
            }}
            
            /* 分组框样式 */
            QGroupBox {{
                background-color: #333333;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                margin-top: 1em;
                padding-top: 1em;
                color: #f0f0f0;
                font-size: {scaled_sizes['normal']}px;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #f0f0f0;
                font-weight: bold;
                background-color: #333333;
                font-size: {scaled_sizes['normal']}px;
            }}
            
            /* 标签样式 */
            QLabel {{
                color: #f0f0f0;
                background-color: transparent;
                border: none;
                font-size: {scaled_sizes['normal']}px;
            }}
            
            /* 按钮样式 */
            QPushButton {{
                background-color: #444444;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px 14px;
                color: #f0f0f0;
                min-width: 80px;
                font-weight: bold;
                font-size: {scaled_sizes['normal']}px;
            }}
            QPushButton:hover {{
                background-color: #505050;
                border-color: #555555;
            }}
            QPushButton:pressed {{
                background-color: #353535;
                border-color: #0078d7;
            }}
            QPushButton:disabled {{
                background-color: #353535;
                color: #777777;
                border-color: #3c3c3c;
            }}
            
            /* 下拉框样式 */
            QComboBox {{
                background-color: #3a3a3a;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 5px;
                color: #f0f0f0;
                min-width: 100px;
                font-size: {scaled_sizes['normal']}px;
            }}
            QComboBox:hover {{
                border: 1px solid #555555;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none; 
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #f0f0f0;
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #3a3a3a;
                border: 1px solid #454545;
                selection-background-color: #0078d7;
                selection-color: #ffffff;
                font-size: {scaled_sizes['normal']}px;
            }}
            
            /* 复选框样式 */
            QCheckBox {{
                color: #f0f0f0;
                spacing: 5px;
                background-color: transparent;
                font-size: {scaled_sizes['normal']}px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #3a3a3a;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0078d7;
                border: 2px solid #0078d7;
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid #777777;
            }}
            
            /* 日期时间编辑器样式 */
            QDateEdit, QTimeEdit, QDateTimeEdit {{
                background-color: #3a3a3a;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 5px;
                color: #f0f0f0;
                font-size: {scaled_sizes['normal']}px;
            }}
            QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
                border: 1px solid #0078d7;
                background-color: #3c3c3c;
            }}
            
            /* 文本编辑器样式 */
            QTextEdit, QPlainTextEdit {{
                background-color: #333333;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #f0f0f0;
                selection-background-color: #0078d7;
                font-family: "Consolas", "Microsoft YaHei", monospace;
                font-size: {scaled_sizes['normal']}px;
            }}
            
            /* 进度条样式 */
            QProgressBar {{
                background-color: #3a3a3a;
                border: 1px solid #454545;
                border-radius: 5px;
                text-align: center;
                font-size: {scaled_sizes['normal']}px;
            }}
            QProgressBar::chunk {{
                background-color: #0078d7;
                border-radius: 4px;
            }}
            
            /* 滚动条样式 */
            QScrollBar:vertical {{
                background-color: #2b2b2b; 
                width: 12px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: #4d4d4d;
                min-height: 20px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #5a5a5a;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background-color: #2b2b2b;
                height: 12px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background-color: #4d4d4d;
                min-width: 20px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: #5a5a5a;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """

    def apply_styles(self):
        """应用样式表"""
        self.setStyleSheet(self.get_scaled_stylesheet())

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用 Fusion 风格
    
    # 设置应用程序图标
    icon_path = os.path.join(ICON_PATH, 'stock_icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = SupplementDataTool()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
