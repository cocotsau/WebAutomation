import sys
import os
import json
import logging
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QListWidget, QTreeWidget, QTreeWidgetItem, QListWidgetItem,
                               QPushButton, QLabel, QMessageBox, QInputDialog, 
                               QMenu, QDialog, QFormLayout, QLineEdit, QComboBox, 
                               QCheckBox, QAbstractItemView, QTabWidget, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
                               QSplitter, QTextEdit, QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QScrollArea, QGridLayout)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QRect, Slot, QObject, QMetaObject, Q_ARG, QEvent, QMimeData, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QIcon, QAction, QCursor, QDrag, QPixmap
from apscheduler.schedulers.qt import QtScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import Engine
from core.workflow_manager import WorkflowManager
from core.element_manager import ElementManager
from tools.basic_tools import PrintLogAction, DelayAction, SetVariableAction
from tools.web_tools import (OpenBrowserAction, CloseBrowserAction, ClickElementAction, 
                             InputTextAction, GoToUrlAction, GetElementInfoAction,
                             HoverElementAction, SwitchFrameAction, ScrollToElementAction, SwitchWindowAction,
                             DrawMousePathAction, HttpDownloadAction,
                             SaveElementAction,
                             WaitElementAction, WaitAllElementsAction)
from tools.logic_tools import (LoopAction, ForEachAction, WhileAction, 
                               IfAction, ElseIfAction, ElseAction, 
                               BreakAction, ContinueAction)
from tools.util_tools import (WaitForFileAndCopyAction, ClearDirectoryAction, OCRImageAction, WeChatNotifyAction)
from tools.excel_tools import (OpenExcelAction, ReadExcelAction, WriteExcelAction, CloseExcelAction, GetExcelRowCountAction, SaveExcelAction)
from gui.widget_factory import WidgetFactory

try:
    from config import browser_config
except ImportError:
    browser_config = None

# Categorized Registry
TOOL_CATEGORIES = {
    "基础工具": {
        "打印日志": PrintLogAction,
        "等待": DelayAction,
        "设置变量": SetVariableAction,
        "计算表达式": None # Placeholder if not imported yet
    },
    "Web 自动化": {
        "打开浏览器": OpenBrowserAction,
        "跳转链接": GoToUrlAction,
        "点击元素": ClickElementAction,
        "输入文本": InputTextAction,
        "获取元素信息": GetElementInfoAction,
        "保存元素": SaveElementAction,
        "悬停在元素上方": HoverElementAction,
        "滚动到元素": ScrollToElementAction,
        "切换 iFrame": SwitchFrameAction,
        "切换窗口": SwitchWindowAction,
        "绘制鼠标轨迹": DrawMousePathAction,
        "HTTP 下载": HttpDownloadAction,
        "等待元素": WaitElementAction,
        "等待全部元素": WaitAllElementsAction,
        "关闭浏览器": CloseBrowserAction
    },
    "Excel 工具": {
        "打开 Excel": OpenExcelAction,
        "读取 Excel": ReadExcelAction,
        "写入 Excel": WriteExcelAction,
        "获取行数": GetExcelRowCountAction,
        "保存 Excel": SaveExcelAction,
        "关闭 Excel": CloseExcelAction
    },
    "逻辑控制": {
        "For循环": LoopAction,
        "Foreach循环": ForEachAction,
        "While循环": WhileAction,
        "If 条件": IfAction,
        "Else If 条件": ElseIfAction,
        "Else 否则": ElseAction,
        "退出循环 (Break)": BreakAction,
        "继续循环 (Continue)": ContinueAction
    },
    "数据与工具": {
        "等待并复制文件": WaitForFileAndCopyAction,
        "清空文件夹": ClearDirectoryAction,
        "OCR 文字识别": OCRImageAction,
        "企业微信通知": WeChatNotifyAction
    }
}

# Import extra tools dynamically if needed or ensure they are imported above
from tools.basic_tools import CalculateAction, FileDialogAction, InputDialogAction
TOOL_CATEGORIES["基础工具"]["计算表达式"] = CalculateAction
TOOL_CATEGORIES["基础工具"]["文件选择"] = FileDialogAction
TOOL_CATEGORIES["基础工具"]["输入对话框"] = InputDialogAction
TOOL_CATEGORIES["数据与工具"]["提取内容"] = None # Will import below
from tools.util_tools import ExtractContentAction
TOOL_CATEGORIES["数据与工具"]["提取内容"] = ExtractContentAction

# Flattened Registry for Engine
ENGINE_REGISTRY = {}
for cat, tools in TOOL_CATEGORIES.items():
    for name, cls in tools.items():
        if cls:
            ENGINE_REGISTRY[name] = cls

LOGIC_TOOLS = ["For循环", "Foreach循环", "While循环", "If 条件", "Else If 条件", "Else 否则"]

class ParameterDialog(QDialog):
    def __init__(self, tool_name, schema, current_params=None, parent=None, scope_anchor=None, extra_context=None):
        super().__init__(parent)
        self.setWindowTitle(f"配置 {tool_name}")
        self.schema = schema
        self.params = current_params or {}
        self.inputs = {}
        self.dependencies = []
        self.resize(480, 420)
        self.scope_anchor = scope_anchor
        self.extra_context = extra_context or {}
        tab_widget = QTabWidget()
        basic_tab = QWidget()
        advanced_tab = QWidget()
        tab_widget.addTab(basic_tab, "基本设置")
        tab_widget.addTab(advanced_tab, "高级设置")
        basic_layout = QFormLayout(basic_tab)
        advanced_layout = QFormLayout(advanced_tab)

        def get_context():
            if self.parent() and hasattr(self.parent(), "gather_context_variables_scoped"):
                return self.parent().gather_context_variables_scoped(self.scope_anchor)
            return {}

        def open_var_picker(target_widget):
            WidgetFactory.open_variable_picker(self, target_widget, get_context)

        for field in schema:
            key = field['name']
            label = field.get('label', key)
            default = field.get('default', '')
            val = self.params.get(key, default)
            target_layout = basic_layout if not field.get('advanced', False) else advanced_layout
            
            inp = WidgetFactory.create_widget(field, val, self, get_context, tool_name)
            
            # Wrap with tools (browse, fx) if necessary
            # We assume WidgetFactory handles basic widget creation, 
            # and we wrap it if it's text-based or needs browse button.
            # But WidgetFactory.create_widget returns just the widget.
            
            final_widget = inp
            if isinstance(inp, (QLineEdit, QTextEdit)):
                final_widget = WidgetFactory.wrap_with_tools(inp, field, self, open_var_picker, extra_context=self.extra_context)
            
            target_layout.addRow(label + ":", final_widget)
            self.inputs[key] = (inp, field['type'])
            
            if 'enable_if' in field:
                self.dependencies.append((key, field['enable_if']))

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab_widget)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("background-color: #409EFF; color: white; border-radius: 4px; padding: 6px 16px;")
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("background-color: #DCDFE6; color: #606266; border-radius: 4px; padding: 6px 16px;")
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        main_layout.addLayout(btn_layout)
        self.setup_dependencies()
        self.setup_special_handlers()

    def setup_dependencies(self):
        for key, (inp, type_str) in self.inputs.items():
            if isinstance(inp, QCheckBox):
                inp.stateChanged.connect(self.check_dependencies)
            elif isinstance(inp, QComboBox):
                inp.currentTextChanged.connect(self.check_dependencies)
            elif isinstance(inp, QLineEdit):
                inp.textChanged.connect(self.check_dependencies)
        self.check_dependencies()

    def check_dependencies(self):
        for target_key, conditions in self.dependencies:
            if target_key not in self.inputs:
                continue
            
            target_widget, _ = self.inputs[target_key]
            # Since target_widget might be wrapped in a container (make_fx_row)
            # we need to find the container if we want to hide the whole row?
            # But here we just setEnabled on the widget itself.
            # The label will remain enabled, which is standard behavior.
            
            enabled = True
            for src_key, required_val in conditions.items():
                if src_key not in self.inputs:
                    continue
                
                src_widget, src_type = self.inputs[src_key]
                current_val = None
                
                if isinstance(src_widget, QCheckBox):
                    current_val = src_widget.isChecked()
                elif isinstance(src_widget, QComboBox):
                    current_val = src_widget.currentText()
                elif isinstance(src_widget, QLineEdit):
                    current_val = src_widget.text()
                    if src_type == 'int':
                        try:
                            current_val = int(current_val)
                        except:
                            pass
                    elif src_type == 'float':
                        try:
                            current_val = float(current_val)
                        except:
                            pass
                
                if current_val != required_val:
                    enabled = False
                    break
            
            target_widget.setEnabled(enabled)

    def setup_special_handlers(self):
        # Special logic for Open Browser: use_local_profile
        if "use_local_profile" in self.inputs and "user_data_dir" in self.inputs:
            chk, _ = self.inputs["use_local_profile"]
            udp_widget, _ = self.inputs["user_data_dir"]
            
            # Find browser_type input if exists
            browser_type_widget = None
            if "browser_type" in self.inputs:
                browser_type_widget, _ = self.inputs["browser_type"]

            def update_udp_state():
                checked = chk.isChecked()
                path_found = False
                
                # Determine browser type
                b_type = "chrome"
                if browser_type_widget and isinstance(browser_type_widget, QComboBox):
                    b_type = browser_type_widget.currentText()
                
                if checked and browser_config and hasattr(browser_config, 'data_dir'):
                    path = browser_config.data_dir.get(b_type, "")
                    if path:
                        path_found = True
                        if isinstance(udp_widget, QLineEdit):
                            udp_widget.setText(path)
                
                # Update UI state
                # If checked and using default path -> ReadOnly + Disabled Browse
                # If checked but no default path found -> Editable? Or empty?
                # User said: "cannot modify when using default directory, can modify when custom directory"
                # "Custom directory" implies maybe unchecking? Or maybe if checked but I want to change it?
                # If I want to change it, I'm NOT using "default directory" anymore, so I should probably uncheck "Use Local Profile" 
                # OR "Use Local Profile" means "Use THE local profile", so if I want custom, I uncheck it.
                # So if Checked -> ReadOnly.
                
                # Wait, user said "custom directory when mutable". 
                # This implies there is a state where I can input custom directory.
                # If "Use Local Profile" is checked, it forces the local profile.
                # If unchecked, I can enter whatever I want (custom).
                # So: Checked -> ReadOnly (and auto-filled). Unchecked -> Editable.
                
                if checked and path_found:
                    if isinstance(udp_widget, QLineEdit):
                        udp_widget.setReadOnly(True)
                        udp_widget.setStyleSheet("background-color: #F5F7FA; color: #909399;")
                    
                    # Disable browse button
                    if udp_widget.parent():
                        for child in udp_widget.parent().findChildren(QPushButton):
                            if child.text() == "...":
                                child.setEnabled(False)
                else:
                    if isinstance(udp_widget, QLineEdit):
                        udp_widget.setReadOnly(False)
                        udp_widget.setStyleSheet("")
                    
                    # Enable browse button
                    if udp_widget.parent():
                        for child in udp_widget.parent().findChildren(QPushButton):
                            if child.text() == "...":
                                child.setEnabled(True)

            chk.stateChanged.connect(update_udp_state)
            if browser_type_widget and isinstance(browser_type_widget, QComboBox):
                browser_type_widget.currentTextChanged.connect(update_udp_state)
            
            # Initial call if checked (it defaults to False, so this might not do much unless default is True)
            # But we should call it to ensure consistent state
            update_udp_state()

    def get_params(self):
        result = {}
        for key, (inp, type_str) in self.inputs.items():
            if isinstance(inp, QComboBox):
                result[key] = inp.currentText()
            elif type_str == 'bool':
                result[key] = inp.isChecked()
            elif type_str == 'int':
                try:
                    result[key] = int(inp.text())
                except:
                    result[key] = 0
            elif type_str == 'float':
                try:
                    result[key] = float(inp.text())
                except:
                    result[key] = 0.0
            elif type_str == 'text':
                result[key] = inp.toPlainText()
            else:
                result[key] = inp.text()
        return result

class ToolBoxTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setStyleSheet("QTreeWidget { border: none; }")

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
            
        # Create standard MimeData for QTreeWidget compatibility
        mime = self.mimeData([item])
        
        drag = QDrag(self)
        drag.setMimeData(mime)
        # No drag pixmap (ghost). Keep interaction minimal.
        drag.exec(supportedActions)

class WorkflowTreeWidget(QTreeWidget):
    tool_dropped = Signal(str, object, int)
    internal_move = Signal(object, object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False) # Disable default indicator to draw custom one
        self.setIndentation(20)
        
        # Track drop target for custom painting
        self.current_drop_target = None
        self.current_drop_indicator = QAbstractItemView.OnItem
        self.current_drop_line_y = None
        self.is_dragging = False

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
        # Only start drag when cursor is inside viewport
        local_pos = self.viewport().mapFromGlobal(QCursor.pos())
        if not self.viewport().rect().contains(local_pos):
            return
        mime = self.mimeData([item])
        drag = QDrag(self)
        drag.setMimeData(mime)
        # Transparent pixmap to remove default dragged item effect
        pm = QPixmap(1, 1)
        pm.fill(Qt.transparent)
        drag.setPixmap(pm)
        self.is_dragging = True
        drag.exec(Qt.MoveAction)
        self.is_dragging = False

    def _indicator_to_int(self, ind):
        if isinstance(ind, int):
            return ind
        if ind == QAbstractItemView.OnItem:
            return 0
        if ind == QAbstractItemView.AboveItem:
            return 1
        if ind == QAbstractItemView.BelowItem:
            return 2
        return 2

    def dragEnterEvent(self, event):
        self.is_dragging = True
        if event.source() == self:
            super().dragEnterEvent(event)
        elif isinstance(event.source(), QTreeWidget):
            super().dragEnterEvent(event)
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        # Disable drop when leaving the widget
        self.current_drop_target = None
        self.viewport().update()
        self.is_dragging = False
        event.ignore()
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        # Restrict drag to viewport area
        if not self.viewport().rect().contains(event.pos()):
            event.ignore()
            return

        # Call super to handle auto-scrolling and default logic
        if event.source() == self:
            super().dragMoveEvent(event)
        elif isinstance(event.source(), QTreeWidget):
            super().dragMoveEvent(event)
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
        else:
            event.ignore()
            return

        # Divider-line driven interaction: snap to nearest divider
        cursor_y = event.pos().y()
        viewport_rect = self.viewport().rect()

        nearest = None  # (item, indicator, line_y, distance)

        def walk_items(parent):
            for i in range(parent.childCount()):
                it = parent.child(i)
                yield it
                # Include children for nested structures
                for sub in walk_items(it):
                    yield sub

        # Gather visible items and their top/bottom divider lines
        root = self.invisibleRootItem()
        for it in walk_items(root):
            rect = self.visualItemRect(it)
            if not rect.isValid():
                continue
            if rect.bottom() < viewport_rect.top() or rect.top() > viewport_rect.bottom():
                continue

            top_y = rect.top()
            bottom_y = rect.bottom()

            # Above divider
            dist_top = abs(cursor_y - top_y)
            if nearest is None or dist_top < nearest[3]:
                nearest = (it, QAbstractItemView.AboveItem, top_y, dist_top)

            # Below divider
            dist_bottom = abs(cursor_y - bottom_y)
            if dist_bottom < nearest[3]:
                nearest = (it, QAbstractItemView.BelowItem, bottom_y, dist_bottom)

        if nearest:
            self.current_drop_target = nearest[0]
            self.current_drop_indicator = nearest[1]
            self.current_drop_line_y = nearest[2]

        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        
        # Draw custom drop indicator
        if self.current_drop_target and self.current_drop_line_y is not None:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Configuration for the indicator
            line_color = QColor("#409EFF")
            line_width = 2
            
            painter.setPen(QPen(line_color, line_width))
            # Draw Line across the entire viewport width at snapped divider
            viewport_width = self.viewport().width()
            painter.drawLine(0, self.current_drop_line_y, viewport_width, self.current_drop_line_y)

    def dropEvent(self, event):
        self.current_drop_target = None
        self.viewport().update()
        self.is_dragging = False

        if event.source() == self:
            item = self.currentItem()
            # Check EndMarker
            data = item.data(0, Qt.UserRole)
            if data and data.get("tool_name") == "EndMarker":
                event.ignore()
                return

            target = self.current_drop_target or self.itemAt(event.pos())
            indicator = self.current_drop_indicator or QAbstractItemView.BelowItem
            indicator_int = self._indicator_to_int(indicator)
            self.internal_move.emit(item, target, indicator_int)
            event.accept()
        elif isinstance(event.source(), QTreeWidget):
            item = event.source().currentItem()
            if item.parent() is None:
                event.ignore()
                return
            
            tool_name = item.text(0)
            target = self.current_drop_target or self.itemAt(event.pos())
            indicator = self.current_drop_indicator or QAbstractItemView.BelowItem
            indicator_int = self._indicator_to_int(indicator)
            self.tool_dropped.emit(tool_name, target, indicator_int)
            event.acceptProposedAction()

def get_relative_time(dt):
    now = datetime.now()
    diff = now - dt
    if diff.days > 365:
        return f"{diff.days // 365}年前"
    if diff.days > 30:
        return f"{diff.days // 30}个月前"
    if diff.days > 0:
        return f"{diff.days}天前"
    if diff.seconds > 3600:
        return f"{diff.seconds // 3600}小时前"
    if diff.seconds > 60:
        return f"{diff.seconds // 60}分钟前"
    return "刚刚"

class StepItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.row_height = 56
        self.icon_colors = {
            "PrintLog": "#909399", "SetVariable": "#E6A23C",
            "OpenExcel": "#67C23A", "ReadExcel": "#67C23A", "WriteExcel": "#67C23A",
            "Loop": "#409EFF", "While": "#409EFF", "Default": "#409EFF",
            "OpenBrowser": "#E6A23C", "ClickElement": "#E6A23C"
        }

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.row_height)

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        
        # Indentation based on nesting depth
        depth = 0
        idx = index
        while idx.parent().isValid():
            depth += 1
            idx = idx.parent()
        indent_offset = depth * 18

        bg_rect = opt.rect
        # Draw background
        tree = self.parent()
        if option.state & QStyle.State_Selected:
            painter.fillRect(bg_rect, QColor("#ECF5FF"))
        elif (option.state & QStyle.State_MouseOver) and (not getattr(tree, "is_dragging", False)):
            painter.fillRect(bg_rect, QColor("#F5F7FA"))
        else:
            painter.fillRect(bg_rect, QColor("#FFFFFF"))

        content_rect = bg_rect.adjusted(10 + indent_offset, 4, -10, -4)
        
        # Data
        data = index.data(Qt.UserRole) or {}
        tool_name = str(data.get("tool_name", index.data(Qt.DisplayRole) or ""))
        params = data.get("params", {})
        is_disabled = bool(data.get("disabled", False))
        if is_disabled:
            painter.setOpacity(0.45)

        # Color & Icon
        color_code = self.icon_colors.get("Default")
        if "Excel" in tool_name: color_code = self.icon_colors["OpenExcel"]
        elif "变量" in tool_name: color_code = self.icon_colors["SetVariable"]
        elif "日志" in tool_name: color_code = self.icon_colors["PrintLog"]
        elif "循环" in tool_name: color_code = self.icon_colors["Loop"]
        elif "浏览器" in tool_name or "元素" in tool_name: color_code = self.icon_colors["OpenBrowser"]
        
        # Icon Box
        icon_rect = QRect(content_rect.left(), content_rect.top() + (content_rect.height()-32)//2, 32, 32)
        painter.setBrush(QColor(color_code))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(icon_rect, 6, 6)
        
        # Icon Text
        painter.setPen(Qt.white)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(icon_rect, Qt.AlignCenter, tool_name[0] if tool_name else "?")
        
        # Title
        title_rect = QRect(icon_rect.right() + 12, content_rect.top() + 4, content_rect.width() - 50, 20)
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#303133"))
        painter.drawText(title_rect, Qt.AlignVCenter | Qt.AlignLeft, tool_name)
        
        # Params
        param_str = ""
        if isinstance(params, dict):
            items = []
            for k, v in params.items():
                items.append(f"{k}={v}")
            param_str = " ".join(items)
        
        subtitle_rect = QRect(icon_rect.right() + 12, title_rect.bottom() + 4, content_rect.width() - 50, 16)
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#909399"))
        
        fm = painter.fontMetrics()
        elided_params = fm.elidedText(param_str, Qt.ElideRight, subtitle_rect.width())
        painter.drawText(subtitle_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_params)

        painter.restore()

class LogSignalHandler(QObject, logging.Handler):
    new_record = Signal(str, str, str) # Time, Level, Message

    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        self.new_record.emit(time_str, record.levelname, msg)

class MainWindow(QMainWindow):
    def __init__(self, manager_ref=None, initial_geometry=None):
        super().__init__()
        self.setWindowTitle("ViewAuto - 智能自动化流程编排")
        if initial_geometry:
            self.setGeometry(initial_geometry)
        else:
            self.resize(1200, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #F2F6FC; }
            QSplitter::handle { background-color: #DCDFE6; width: 1px; }
            QTreeWidget { border: none; background-color: #FFFFFF; }
            QTreeWidget::item { padding: 4px; }
            QTabWidget::pane { border: 1px solid #DCDFE6; background: white; }
            QTabBar::tab { background: #F5F7FA; border: 1px solid #DCDFE6; padding: 8px 12px; }
            QTabBar::tab:selected { background: white; border-bottom: none; }
        """)
        
        # Managers
        self.workflow_manager = WorkflowManager()
        self.engine = Engine()
        
        # Element Managers
        self.global_element_manager = ElementManager("elements.json")
        self.private_element_manager = ElementManager(None) # Init with no file until workflow loaded

        # Scheduler
        self.scheduler = QtScheduler()
        self.scheduler.start()
        
        # Log Handler
        self.log_handler = LogSignalHandler()
        self.log_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(self.log_handler)
        self.log_handler.new_record.connect(self.add_log_record)
        
        # Main Layout using Splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(1)
        self.setCentralWidget(main_splitter)

        # --- Left Panel: Toolbox ---
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(200)
        self.left_panel.setStyleSheet("background-color: white;")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Tab Widget for Toolbox / Saved
        self.left_tabs = QTabWidget()
        self.left_tabs.setTabPosition(QTabWidget.South)
        
        # Toolbox Tab
        toolbox_widget = QWidget()
        toolbox_layout = QVBoxLayout(toolbox_widget)
        toolbox_layout.setContentsMargins(0, 0, 0, 0)
        
        self.toolbox_tree = ToolBoxTree()
        self.toolbox_tree.setHeaderHidden(True)
        self.toolbox_tree.setDragEnabled(True)
        self.toolbox_tree.setDragDropMode(QAbstractItemView.DragOnly)
        self.toolbox_tree.itemDoubleClicked.connect(self.add_tool_to_workflow)
        self.toolbox_tree.itemClicked.connect(self.handle_toolbox_item_clicked)
        self.toolbox_tree.setStyleSheet("QTreeWidget { border: none; }")
        
        for category, tools in TOOL_CATEGORIES.items():
            cat_item = QTreeWidgetItem([category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsDragEnabled)
            cat_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            cat_item.setForeground(0, QBrush(QColor("#303133")))
            
            for tool_name in tools.keys():
                tool_item = QTreeWidgetItem([tool_name])
                tool_item.setData(0, Qt.UserRole, "tool")
                tool_item.setFlags(tool_item.flags() | Qt.ItemIsDragEnabled)
                tool_item.setFont(0, QFont("Arial", 9))
                tool_item.setForeground(0, QBrush(QColor("#606266")))
                cat_item.addChild(tool_item)
            
            self.toolbox_tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(False)
            
        toolbox_layout.addWidget(self.toolbox_tree)
        self.left_tabs.addTab(toolbox_widget, "组件库")
        
        # Manager reference for back navigation
        self.manager_ref = manager_ref
        
        left_layout.addWidget(self.left_tabs)
        main_splitter.addWidget(self.left_panel)

        # --- Right Panel: Workflow + Logs ---
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(1)
        
        # Top Right: Workflow Editor
        self.workflow_container = QWidget()
        self.workflow_container.setStyleSheet("background-color: white;")
        workflow_layout = QVBoxLayout(self.workflow_container)
        workflow_layout.setContentsMargins(0, 0, 0, 0)
        workflow_layout.setSpacing(0)
        
        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #F5F7FA; border-bottom: 1px solid #DCDFE6;")
        toolbar.setFixedHeight(50)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        
        # Back button
        self.btn_back = self.create_toolbar_btn("返回", "#909399")
        self.btn_back.clicked.connect(self.handle_back_to_manager)
        
        self.btn_save = self.create_toolbar_btn("保存", "#67C23A")
        self.btn_save.clicked.connect(self.save_workflow_dialog)
        
        self.btn_run = self.create_toolbar_btn("运行", "#409EFF")
        self.btn_run.clicked.connect(lambda: self.run_workflow())

        self.btn_schedule = self.create_toolbar_btn("定时 (9:00)", "#E6A23C")
        try:
            if hasattr(self, "toggle_schedule"):
                self.btn_schedule.clicked.connect(self.toggle_schedule)
            else:
                self.btn_schedule.setEnabled(False)
        except Exception:
            self.btn_schedule.setEnabled(False)
        
        self.btn_clear = self.create_toolbar_btn("清空", "#F56C6C")
        self.btn_clear.clicked.connect(self.confirm_clear_workflow)
        
        self.btn_undo = self.create_toolbar_btn("撤销", "#909399")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.perform_undo)
        
        toolbar_layout.addWidget(self.btn_back)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_run)
        toolbar_layout.addWidget(self.btn_schedule)
        toolbar_layout.addWidget(self.btn_clear)
        toolbar_layout.addWidget(self.btn_undo)
        toolbar_layout.addStretch()
        
        workflow_layout.addWidget(toolbar)
        
        # Workflow Tree
        self.workflow_tree = WorkflowTreeWidget()
        self.workflow_tree.setHeaderLabel("流程步骤")
        self.workflow_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.workflow_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        try:
            if hasattr(self, "show_context_menu"):
                self.workflow_tree.customContextMenuRequested.connect(self.show_context_menu)
            else:
                # Fallback: disable context menu if handler missing
                self.workflow_tree.setContextMenuPolicy(Qt.NoContextMenu)
        except Exception:
            self.workflow_tree.setContextMenuPolicy(Qt.NoContextMenu)
        self.workflow_tree.tool_dropped.connect(self.handle_tool_drop)
        self.workflow_tree.internal_move.connect(self.handle_internal_move)
        self.workflow_tree.setItemDelegate(StepItemDelegate(self.workflow_tree))
        self.workflow_tree.setUniformRowHeights(False)
        self.workflow_tree.setStyleSheet("QTreeWidget { border: none; }")
        try:
            if hasattr(self, "handle_item_collapsed"):
                self.workflow_tree.itemCollapsed.connect(self.handle_item_collapsed)
            if hasattr(self, "handle_item_expanded"):
                self.workflow_tree.itemExpanded.connect(self.handle_item_expanded)
        except Exception:
            pass
        self.workflow_tree.itemDoubleClicked.connect(self.edit_step_on_double_click)
        
        workflow_layout.addWidget(self.workflow_tree)
        right_splitter.addWidget(self.workflow_container)
        
        # Bottom Right: Logs
        self.log_panel = QWidget()
        self.log_panel.setStyleSheet("background-color: white;")
        log_layout = QVBoxLayout(self.log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)
        
        log_header = QLabel("  运行日志")
        log_header.setFixedHeight(30)
        log_header.setStyleSheet("background-color: #F5F7FA; border-bottom: 1px solid #DCDFE6; font-weight: bold;")
        log_layout.addWidget(log_header)
        
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["时间", "级别", "消息"])
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.log_table.setStyleSheet("border: none;")
        
        log_layout.addWidget(self.log_table)
        right_splitter.addWidget(self.log_panel)
        
        main_splitter.addWidget(right_splitter)
        
        # Factors
        main_splitter.setStretchFactor(0, 1) # Left
        main_splitter.setStretchFactor(1, 4) # Right
        right_splitter.setStretchFactor(0, 3) # Workflow
        right_splitter.setStretchFactor(1, 1) # Logs

        # Status Bar
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label)
    def gather_context_variables(self):
        vars_set = set()
        try:
            for k in self.engine.context.keys():
                vars_set.add(str(k))
        except:
            pass
        vars_set.add("loop_index")
        root = self.workflow_tree.invisibleRootItem()
        def walk(parent):
            for i in range(parent.childCount()):
                it = parent.child(i)
                yield it
                for sub in walk(it):
                    yield sub
        for it in walk(root):
            data = it.data(0, Qt.UserRole) or {}
            params = data.get("params", {}) or {}
            for k, v in params.items():
                if isinstance(v, str):
                    if k.endswith("output_variable") or k.endswith("_variable") or k in ("output_variable","driver_variable","item_variable","list_variable"):
                        vars_set.add(v)
        return sorted(vars_set)
    def gather_context_variables_scoped(self, anchor):
        def is_end_marker(it):
            d = it.data(0, Qt.UserRole) or {}
            return d.get("tool_name") == "EndMarker"
        def is_loop_tool_name(n):
            return n in ("For循环", "Foreach循环", "While循环")
        def add_vars_from_item(it, into):
            d = it.data(0, Qt.UserRole) or {}
            tname = d.get("tool_name")
            p = d.get("params", {}) or {}
            for k, v in p.items():
                if isinstance(v, str) and v and (k.endswith("output_variable") or k.endswith("_variable") or k in ("output_variable","driver_variable","item_variable","list_variable")):
                    # Determine type
                    v_type = "一般变量"
                    if k == "output_variable":
                        if tname == "Open Browser": v_type = "网页对象"
                        elif tname == "Open Excel": v_type = "Excel对象"
                    elif k == "driver_variable":
                         # If it's a usage, we can't be sure if it's defined as such, but we can hint it
                         # But better to leave it as is if already defined. 
                         # If not defined, assume it's a web object because it's used as one.
                         if v not in into: v_type = "网页对象"
                         else: continue # Already defined
                    
                    if v not in into:
                        into[v] = v_type
                    elif into[v] == "一般变量" and v_type != "一般变量":
                        # Upgrade type if we found a better definition
                        into[v] = v_type

        vars_map = {}
        root = self.workflow_tree.invisibleRootItem()
        stop_after_subtree = [False]
        target_item = None
        indicator = None
        mode = None
        if anchor and isinstance(anchor, tuple):
            mode = anchor[0]
            if mode == 'edit':
                target_item = anchor[1]
            elif mode == 'add':
                target_item = anchor[1]
                indicator = anchor[2]
        def has_ancestor_loop(it):
            cur = it.parent() if it else None
            while cur:
                d = cur.data(0, Qt.UserRole) or {}
                n = d.get("tool_name")
                if n and is_loop_tool_name(n):
                    return True
                cur = cur.parent()
            return False
        def within_loop_children():
            if not target_item:
                return False
            d = target_item.data(0, Qt.UserRole) or {}
            tname = d.get("tool_name")
            if mode == 'edit':
                return has_ancestor_loop(target_item)
            if mode == 'add':
                if tname and is_loop_tool_name(tname):
                    return indicator == QAbstractItemView.OnItem
                return has_ancestor_loop(target_item)
            return False
        def traverse(parent):
            for i in range(parent.childCount()):
                it = parent.child(i)
                if is_end_marker(it):
                    continue
                if mode == 'edit' and it is target_item:
                    return True
                if mode == 'add' and it is target_item:
                    if indicator == QAbstractItemView.AboveItem:
                        return True
                    add_vars_from_item(it, vars_map)
                    for j in range(it.childCount()):
                        sub = it.child(j)
                        if not is_end_marker(sub):
                            add_vars_from_item(sub, vars_map)
                            if traverse(sub):
                                return True
                    return True
                add_vars_from_item(it, vars_map)
                if traverse(it):
                    return True
            return False
        traverse(root)
        if within_loop_children():
            vars_map["loop_index"] = "循环变量"
            vars_map["item"] = "循环项"
        return vars_map

    def create_toolbar_btn(self, text, color):
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            QPushButton:pressed {{
                opacity: 0.8;
            }}
            QPushButton:disabled {{
                background-color: #E4E7ED;
                color: #C0C4CC;
            }}
        """)
        return btn

    @Slot(str, str, str)
    def add_log_record(self, time_str, level, msg):
        if not hasattr(self, "log_table"):
            return
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        
        item_time = QTableWidgetItem(time_str)
        item_level = QTableWidgetItem(level)
        item_msg = QTableWidgetItem(msg)
        
        if level == "ERROR":
            item_level.setForeground(QColor("#F56C6C"))
            item_msg.setForeground(QColor("#F56C6C"))
        elif level == "WARNING":
            item_level.setForeground(QColor("#E6A23C"))
        
        self.log_table.setItem(row, 0, item_time)
        self.log_table.setItem(row, 1, item_level)
        self.log_table.setItem(row, 2, item_msg)
        self.log_table.scrollToBottom()

    def create_undo_snapshot(self):
        self.undo_snapshot = self.get_workflow_data()
        self.btn_undo.setEnabled(True)

    def perform_undo(self):
        snapshot = getattr(self, "undo_snapshot", None)
        if not snapshot:
            QMessageBox.information(self, "提示", "没有可撤销的内容。")
            return
        
        self.workflow_tree.clear()
        self.load_workflow_to_tree(snapshot)
        self.undo_snapshot = None
        self.btn_undo.setEnabled(False)
        self.status_label.setText("已撤销上一步操作。")

    def confirm_clear_workflow(self):
        if self.workflow_tree.topLevelItemCount() == 0:
            QMessageBox.information(self, "提示", "当前没有步骤可清空。")
            return
        res = QMessageBox.question(self, "确认清空", "确定清空所有步骤？此操作会删除当前编辑内容。", QMessageBox.Yes | QMessageBox.No)
        if res != QMessageBox.Yes:
            return
            
        self.create_undo_snapshot()
        self.workflow_tree.clear()
        self.status_label.setText("已清空，可撤销。")

    def init_saved_workflows_tab(self):
        self.saved_tab = QWidget()
        layout = QVBoxLayout(self.saved_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.saved_workflows_tree = QTreeWidget()
        self.saved_workflows_tree.setHeaderHidden(True)
        self.saved_workflows_tree.itemDoubleClicked.connect(self.load_saved_workflow_item)
        self.saved_workflows_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.saved_workflows_tree.customContextMenuRequested.connect(self.show_saved_workflows_context_menu)
        self.saved_workflows_tree.setStyleSheet("border: none;")
        
        layout.addWidget(self.saved_workflows_tree)
        
        btn_refresh = QPushButton("刷新列表")
        btn_refresh.clicked.connect(self.refresh_saved_workflows_list)
        layout.addWidget(btn_refresh)
        
        self.left_tabs.addTab(self.saved_tab, "流程管理")
        self.refresh_saved_workflows_list()

    def refresh_saved_workflows_list(self):
        self.saved_workflows_tree.clear()
        workflows = self.workflow_manager.list_workflows()
        
        for group, items in workflows.items():
            group_item = QTreeWidgetItem([group])
            group_item.setData(0, Qt.UserRole, {"type": "group", "name": group})
            group_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            
            for wf_name in items:
                wf_item = QTreeWidgetItem([wf_name])
                wf_item.setData(0, Qt.UserRole, {"type": "workflow", "name": wf_name, "group": group})
                group_item.addChild(wf_item)
                
            self.saved_workflows_tree.addTopLevelItem(group_item)
            group_item.setExpanded(True)

    def save_workflow_dialog(self):
        workflow_data = self.get_workflow_data()
        if not workflow_data:
            QMessageBox.warning(self, "警告", "无法保存空流程！")
            return
        
        # If current workflow has identity, save directly (update)
        current_name = getattr(self, "current_workflow_name", None)
        current_group = getattr(self, "current_workflow_group", None)
        if current_name and current_group:
            if self.workflow_manager.save_workflow(current_name, current_group, workflow_data):
                # Ensure private element manager path aligns and persist any existing cache
                new_elements_path = os.path.join("workflows", current_group, f"{current_name}.elements.json")
                current_data = self.private_element_manager._read_all()
                self.private_element_manager.set_file_path(new_elements_path, load_now=False)
                if current_data:
                    self.private_element_manager._write_all(current_data)
                QMessageBox.information(self, "成功", f"流程 {current_group}/{current_name} 已更新保存。")
                self.refresh_saved_workflows_list()
                return
            else:
                QMessageBox.critical(self, "错误", "保存失败，请检查名称是否合法。")
                return

        dlg = QDialog(self)
        dlg.setWindowTitle("保存流程")
        layout = QFormLayout(dlg)
        
        name_edit = QLineEdit()
        group_edit = QComboBox()
        group_edit.setEditable(True)
        
        existing_groups = self.workflow_manager.get_all_groups()
        group_edit.addItems(existing_groups)
        if not existing_groups:
             group_edit.addItem("Default")
        
        layout.addRow("流程名称:", name_edit)
        layout.addRow("分组:", group_edit)
        
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("保存")
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dlg.reject)
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addRow(btn_box)
        
        if dlg.exec():
            name = name_edit.text().strip()
            group = group_edit.currentText().strip()
            
            if not name or not group:
                QMessageBox.warning(self, "错误", "名称和分组不能为空！")
                return
                
            if self.workflow_manager.save_workflow(name, group, workflow_data):
                # Update private element manager path to match new save location
                new_elements_path = os.path.join("workflows", group, f"{name}.elements.json")
                # If we were working with a temporary or different path, we should probably save current data to new path
                # But ElementManager.set_file_path(path) just switches. 
                # We should explicitly save current cache to the new path.
                
                # Check if we need to migrate data? 
                # If self.private_element_manager already has data (from editing session), 
                # we want to save it to the new file.
                current_data = self.private_element_manager._read_all()
                self.private_element_manager.set_file_path(new_elements_path, load_now=False)
                if current_data:
                    self.private_element_manager._write_all(current_data)
                
                QMessageBox.information(self, "成功", f"流程 {name} 保存成功！")
                self.refresh_saved_workflows_list()
                # Set current workflow identity for subsequent quick saves
                self.current_workflow_name = name
                self.current_workflow_group = group
            else:
                QMessageBox.critical(self, "错误", "保存失败，请检查名称是否合法。")

    def load_saved_workflow_item(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "workflow":
            name = data["name"]
            group = data["group"]
            self.load_workflow(name, group)

    def show_saved_workflows_context_menu(self, pos):
        item = self.saved_workflows_tree.itemAt(pos)
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        if not data:
            return
            
        menu = QMenu(self)
        if data["type"] == "workflow":
            load_action = menu.addAction("加载")
            delete_action = menu.addAction("删除")
            action = menu.exec(self.saved_workflows_tree.mapToGlobal(pos))
            
            if action == load_action:
                self.load_workflow(data["name"], data["group"])
            elif action == delete_action:
                res = QMessageBox.question(self, "确认删除", f"确定删除流程 {data['name']}？", QMessageBox.Yes | QMessageBox.No)
                if res == QMessageBox.Yes:
                    self.workflow_manager.delete_workflow(data["name"], data["group"])
                    self.refresh_saved_workflows_list()

    def load_workflow(self, name, group):
        workflow_data = self.workflow_manager.load_workflow(name, group)
        if workflow_data:
            self.create_undo_snapshot()
            
            # Setup private element manager
            elements_path = os.path.join("workflows", group, f"{name}.elements.json")
            self.private_element_manager.set_file_path(elements_path)
            
            self.workflow_tree.clear()
            self.load_workflow_to_tree(workflow_data)
            self.status_label.setText(f"已加载流程: {group}/{name}")
            self.current_workflow_name = name
            self.current_workflow_group = group
            # After loading a workflow in editor, show back button if manager exists
            self.btn_back.setVisible(bool(self.manager_ref))
    
    def handle_back_to_manager(self):
        if self.manager_ref:
            try:
                rect = self.geometry()
                self.manager_ref.setGeometry(rect)
                self.manager_ref.show()
                if hasattr(self.manager_ref, "refresh"):
                    self.manager_ref.refresh()
            except Exception:
                pass
        self.close()

    def add_tool_to_workflow(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data == "tool":
            tool_name = item.text(0)
            self.add_step(tool_name)

    def handle_toolbox_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data == "tool":
            return
        item.setExpanded(not item.isExpanded())

    def handle_tool_drop(self, tool_name, target_item, indicator):
        try:
            if isinstance(indicator, int):
                indicator = QAbstractItemView.DropIndicatorPosition(indicator)
        except Exception:
            pass
        if not target_item:
            self.add_step(tool_name)
        else:
            self.add_step(tool_name, target_item, indicator)

    def handle_internal_move(self, item, target_item, indicator):
        try:
            if isinstance(indicator, int):
                indicator = QAbstractItemView.DropIndicatorPosition(indicator)
        except Exception:
            pass

        if target_item:
            data = target_item.data(0, Qt.UserRole)
            if data and data.get("tool_name") == "EndMarker":
                if indicator == QAbstractItemView.BelowItem:
                    pass
                else:
                    parent = target_item.parent()
                    index = parent.indexOfChild(target_item) if parent else self.workflow_tree.indexOfTopLevelItem(target_item)
                    logic_tool = None
                    if index > 0:
                        if parent:
                            logic_tool = parent.child(index - 1)
                        else:
                            logic_tool = self.workflow_tree.topLevelItem(index - 1)
                    if logic_tool:
                        target_item = logic_tool
                        indicator = QAbstractItemView.OnItem

        if target_item and indicator == QAbstractItemView.OnItem:
            t_data = target_item.data(0, Qt.UserRole)
            t_name = t_data.get("tool_name") if t_data else None
            if t_name and t_name not in LOGIC_TOOLS:
                indicator = QAbstractItemView.BelowItem

        end_marker_to_move = None
        item_data = item.data(0, Qt.UserRole)
        if item_data and item_data.get("tool_name") in LOGIC_TOOLS:
            parent = item.parent()
            index = parent.indexOfChild(item) if parent else self.workflow_tree.indexOfTopLevelItem(item)
            next_sibling = None
            if parent:
                if index + 1 < parent.childCount():
                    next_sibling = parent.child(index + 1)
            else:
                if index + 1 < self.workflow_tree.topLevelItemCount():
                    next_sibling = self.workflow_tree.topLevelItem(index + 1)
            if next_sibling:
                ns_data = next_sibling.data(0, Qt.UserRole)
                if ns_data and ns_data.get("tool_name") == "EndMarker":
                    end_marker_to_move = next_sibling

        current_parent = item.parent()
        if current_parent:
            current_parent.removeChild(item)
            if end_marker_to_move:
                current_parent.removeChild(end_marker_to_move)
        else:
            index = self.workflow_tree.indexOfTopLevelItem(item)
            self.workflow_tree.takeTopLevelItem(index)
            if end_marker_to_move:
                em_index = self.workflow_tree.indexOfTopLevelItem(end_marker_to_move)
                if em_index != -1:
                    self.workflow_tree.takeTopLevelItem(em_index)

        if target_item:
            parent = target_item.parent()
            if indicator == QAbstractItemView.OnItem:
                target_item.addChild(item)
                target_item.setExpanded(True)
                if end_marker_to_move:
                    target_item.addChild(end_marker_to_move)
            elif indicator == QAbstractItemView.AboveItem:
                if parent:
                    index = parent.indexOfChild(target_item)
                    parent.insertChild(index, item)
                    if end_marker_to_move:
                        parent.insertChild(index + 1, end_marker_to_move)
                else:
                    index = self.workflow_tree.indexOfTopLevelItem(target_item)
                    self.workflow_tree.insertTopLevelItem(index, item)
                    if end_marker_to_move:
                        self.workflow_tree.insertTopLevelItem(index + 1, end_marker_to_move)
            elif indicator == QAbstractItemView.BelowItem:
                if parent:
                    index = parent.indexOfChild(target_item)
                    parent.insertChild(index + 1, item)
                    if end_marker_to_move:
                        parent.insertChild(index + 2, end_marker_to_move)
                else:
                    index = self.workflow_tree.indexOfTopLevelItem(target_item)
                    self.workflow_tree.insertTopLevelItem(index + 1, item)
                    if end_marker_to_move:
                        self.workflow_tree.insertTopLevelItem(index + 2, end_marker_to_move)
        else:
            self.workflow_tree.addTopLevelItem(item)
            if end_marker_to_move:
                self.workflow_tree.addTopLevelItem(end_marker_to_move)
        self.create_undo_snapshot()
    def add_step(self, tool_name, target_item=None, indicator=None, existing_params=None):
        tool_cls = ENGINE_REGISTRY.get(tool_name)
        if not tool_cls:
            return
        try:
            if isinstance(indicator, int):
                indicator = QAbstractItemView.DropIndicatorPosition(indicator)
        except Exception:
            pass
        schema = tool_cls().get_param_schema()
        params = existing_params or {}
        if schema and existing_params is None:
            extra_context = {
                "element_manager_private": self.private_element_manager,
                "element_manager_global": self.global_element_manager
            }
            dlg = ParameterDialog(tool_name, schema, parent=self, scope_anchor=('add', target_item, indicator), extra_context=extra_context)
            if dlg.exec():
                params = dlg.get_params()
            else:
                return
        if target_item:
            data = target_item.data(0, Qt.UserRole)
            if data and data.get("tool_name") == "EndMarker":
                if indicator == QAbstractItemView.BelowItem:
                    pass
                else:
                    parent = target_item.parent()
                    index = parent.indexOfChild(target_item) if parent else self.workflow_tree.indexOfTopLevelItem(target_item)
                    logic_tool = None
                    if index > 0:
                        if parent:
                            logic_tool = parent.child(index - 1)
                        else:
                            logic_tool = self.workflow_tree.topLevelItem(index - 1)
                    if logic_tool:
                        target_item = logic_tool
                        indicator = QAbstractItemView.OnItem
        if target_item and indicator == QAbstractItemView.OnItem:
            t_data = target_item.data(0, Qt.UserRole)
            t_name = t_data.get("tool_name") if t_data else None
            if t_name and t_name not in LOGIC_TOOLS:
                indicator = QAbstractItemView.BelowItem
        item = QTreeWidgetItem([tool_name])
        item.setData(0, Qt.UserRole, {"tool_name": tool_name, "params": params})
        if target_item:
            parent = target_item.parent()
            if indicator == QAbstractItemView.OnItem:
                target_item.addChild(item)
                target_item.setExpanded(True)
            elif indicator == QAbstractItemView.AboveItem:
                if parent:
                    index = parent.indexOfChild(target_item)
                    parent.insertChild(index, item)
                else:
                    index = self.workflow_tree.indexOfTopLevelItem(target_item)
                    self.workflow_tree.insertTopLevelItem(index, item)
            elif indicator == QAbstractItemView.BelowItem:
                if parent:
                    index = parent.indexOfChild(target_item)
                    parent.insertChild(index + 1, item)
                else:
                    index = self.workflow_tree.indexOfTopLevelItem(target_item)
                    self.workflow_tree.insertTopLevelItem(index + 1, item)
        else:
            self.workflow_tree.addTopLevelItem(item)
        if tool_name in LOGIC_TOOLS:
            end_item = QTreeWidgetItem([f"结束 {tool_name}"])
            end_item.setData(0, Qt.UserRole, {"tool_name": "EndMarker", "params": {}})
            end_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            parent = item.parent()
            if parent:
                index = parent.indexOfChild(item)
                parent.insertChild(index + 1, end_item)
            else:
                index = self.workflow_tree.indexOfTopLevelItem(item)
                self.workflow_tree.insertTopLevelItem(index + 1, end_item)
            item.setExpanded(True)
        self.create_undo_snapshot()

    def show_context_menu(self, pos):
        item = self.workflow_tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if data and data.get("tool_name") == "EndMarker":
            return
        menu = QMenu(self)
        edit_action = menu.addAction("编辑参数")
        delete_action = menu.addAction("删除步骤")
        disabled = (data or {}).get("disabled", False)
        toggle_disable_action = menu.addAction("启用步骤" if disabled else "禁用步骤")
        action = menu.exec(self.workflow_tree.mapToGlobal(pos))
        if action == edit_action:
            self.edit_step(item)
        elif action == delete_action:
            self.create_undo_snapshot()
            parent = item.parent()
            data = item.data(0, Qt.UserRole) or {}
            name = data.get("tool_name")
            if parent:
                if name in LOGIC_TOOLS:
                    idx = parent.indexOfChild(item)
                    if idx + 1 < parent.childCount():
                        sib = parent.child(idx + 1)
                        sdata = sib.data(0, Qt.UserRole) or {}
                        if sdata.get("tool_name") == "EndMarker":
                            parent.removeChild(sib)
                parent.removeChild(item)
            else:
                if name in LOGIC_TOOLS:
                    idx = self.workflow_tree.indexOfTopLevelItem(item)
                    if idx + 1 < self.workflow_tree.topLevelItemCount():
                        sib = self.workflow_tree.topLevelItem(idx + 1)
                        sdata = sib.data(0, Qt.UserRole) or {}
                        if sdata.get("tool_name") == "EndMarker":
                            em_idx = self.workflow_tree.indexOfTopLevelItem(sib)
                            if em_idx != -1:
                                self.workflow_tree.takeTopLevelItem(em_idx)
                idx = self.workflow_tree.indexOfTopLevelItem(item)
                if idx != -1:
                    self.workflow_tree.takeTopLevelItem(idx)
        elif action == toggle_disable_action:
            self.create_undo_snapshot()
            d = item.data(0, Qt.UserRole) or {}
            d["disabled"] = not d.get("disabled", False)
            item.setData(0, Qt.UserRole, d)
            self.workflow_tree.viewport().update()

    def edit_step(self, item):
        data = item.data(0, Qt.UserRole)
        tool_name = data["tool_name"]
        params = data["params"]
        tool_cls = ENGINE_REGISTRY.get(tool_name)
        schema = tool_cls().get_param_schema()
        if schema:
            extra_context = {
                "element_manager_private": self.private_element_manager,
                "element_manager_global": self.global_element_manager
            }
            dlg = ParameterDialog(tool_name, schema, current_params=params, parent=self, scope_anchor=('edit', item), extra_context=extra_context)
            if dlg.exec():
                new_params = dlg.get_params()
                data["params"] = new_params
                item.setData(0, Qt.UserRole, data)

    def edit_step_on_double_click(self, item, column):
        if not item:
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("tool_name") == "EndMarker":
            return
        self.edit_step(item)

    def handle_item_collapsed(self, item):
        data = item.data(0, Qt.UserRole) or {}
        name = data.get("tool_name")
        if not name or name not in LOGIC_TOOLS:
            return
        parent = item.parent()
        if parent:
            idx = parent.indexOfChild(item)
            if idx + 1 < parent.childCount():
                sib = parent.child(idx + 1)
                sdata = sib.data(0, Qt.UserRole) or {}
                if sdata.get("tool_name") == "EndMarker":
                    sib.setHidden(True)
        else:
            idx = self.workflow_tree.indexOfTopLevelItem(item)
            if idx + 1 < self.workflow_tree.topLevelItemCount():
                sib = self.workflow_tree.topLevelItem(idx + 1)
                sdata = sib.data(0, Qt.UserRole) or {}
                if sdata.get("tool_name") == "EndMarker":
                    sib.setHidden(True)

    def handle_item_expanded(self, item):
        data = item.data(0, Qt.UserRole) or {}
        name = data.get("tool_name")
        if not name or name not in LOGIC_TOOLS:
            return
        parent = item.parent()
        if parent:
            idx = parent.indexOfChild(item)
            if idx + 1 < parent.childCount():
                sib = parent.child(idx + 1)
                sdata = sib.data(0, Qt.UserRole) or {}
                if sdata.get("tool_name") == "EndMarker":
                    sib.setHidden(False)
        else:
            idx = self.workflow_tree.indexOfTopLevelItem(item)
            if idx + 1 < self.workflow_tree.topLevelItemCount():
                sib = self.workflow_tree.topLevelItem(idx + 1)
                sdata = sib.data(0, Qt.UserRole) or {}
                if sdata.get("tool_name") == "EndMarker":
                    sib.setHidden(False)
    def get_workflow_data(self):
        return self.get_items_data(self.workflow_tree.invisibleRootItem())

    def get_items_data(self, parent_item):
        steps = []
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            data = item.data(0, Qt.UserRole)
            
            if data.get("tool_name") == "EndMarker":
                continue
                
            step_data = {
                "tool_name": data["tool_name"],
                "params": data["params"],
                "disabled": bool(data.get("disabled", False)),
                "children": self.get_items_data(item)
            }
            steps.append(step_data)
        return steps

    def load_workflow_to_tree(self, workflow_data, parent_item=None):
        if parent_item is None:
            parent_item = self.workflow_tree.invisibleRootItem()
            
        for step in workflow_data:
            item = QTreeWidgetItem([step["tool_name"]])
            item.setData(0, Qt.UserRole, {"tool_name": step["tool_name"], "params": step["params"]})
            parent_item.addChild(item)
            
            if step.get("children"):
                self.load_workflow_to_tree(step["children"], item)
                
            if step["tool_name"] in LOGIC_TOOLS:
                end_item = QTreeWidgetItem([f"结束 {step['tool_name']}"])
                end_item.setData(0, Qt.UserRole, {"tool_name": "EndMarker", "params": {}})
                end_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                parent_item.addChild(end_item)
            
            item.setExpanded(True)

    def toggle_schedule(self):
        job_id = "daily_workflow_job"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            self.btn_schedule.setText("定时 (9:00)")
            self.btn_schedule.setStyleSheet(self.btn_schedule.styleSheet().replace("#67C23A", "#E6A23C"))
            QMessageBox.information(self, "定时任务", "已取消定时任务。")
        else:
            workflow_data = self.get_workflow_data()
            if not workflow_data:
                QMessageBox.warning(self, "警告", "流程为空，无法设置定时任务！")
                return
            
            # Add job
            trigger = CronTrigger(hour=9, minute=0)
            self.scheduler.add_job(
                self.engine.run, # Note: This runs in scheduler thread. 
                # Ideally we should use a wrapper to load workflow first?
                # The engine state is persistent. 
                # But wait, self.engine.run() uses self.workflow_data.
                # We need to set it.
                trigger=trigger,
                id=job_id,
                name="Daily Workflow"
            )
            
            # We need to ensure engine has the workflow loaded when it runs.
            # But engine.load_workflow is just setting attributes.
            # So we can wrap it.
            self.scheduler.modify_job(job_id, func=self.run_workflow_scheduled, args=[workflow_data])
            
            self.btn_schedule.setText("已定时 (9:00)")
            # Change color to green to indicate active
            self.btn_schedule.setStyleSheet(self.btn_schedule.styleSheet().replace("#E6A23C", "#67C23A"))
            QMessageBox.information(self, "定时任务", "已设置每天 9:00 运行此流程。")

    def run_workflow_scheduled(self, workflow_data):
        # This runs in background thread by APScheduler
        try:
            logging.info("Starting scheduled workflow...")
            self.engine.load_workflow(workflow_data, ENGINE_REGISTRY)
            self.engine.run()
        except Exception as e:
            logging.error(f"Scheduled Run Error: {e}")

    def run_workflow(self):
        workflow_data = self.get_workflow_data()
        if not workflow_data:
            QMessageBox.warning(self, "提示", "流程为空！")
            return
            
        self.log_table.setRowCount(0)
        self.status_label.setText("正在运行...")
        
        # Disable buttons
        self.btn_run.setEnabled(False)
        self.btn_save.setEnabled(False)
        
        # Use QTimer to run async to not freeze UI completely (simple approach)
        # Ideally should use QThread, but Engine is synchronous. 
        # For now, we rely on Engine logging and ProcessEvents if inserted, but Engine blocks.
        # To show logs in real-time, we need a thread.
        
        import threading
        t = threading.Thread(target=self._run_thread, args=(workflow_data,))
        t.start()

    def _run_thread(self, workflow_data):
        try:
            self.engine.load_workflow(workflow_data, ENGINE_REGISTRY)
            
            # Inject element managers
            self.engine.context["element_manager_private"] = self.private_element_manager
            self.engine.context["element_manager_global"] = self.global_element_manager
            
            self.engine.run()
            # UI updates must be done via signals or slots, but status_label setText is not thread safe?
            # Actually PySide6 signals are thread safe.
            # But setText directly is not.
            # We will use a timer or signal for completion.
        except Exception as e:
            logging.error(f"Run Error: {e}")
        finally:
            # We need to re-enable buttons. 
            # Since we are in a thread, we can't touch UI.
            # Let's emit a signal or use QMetaObject.invokeMethod, 
            # but simpler is to use a QTimer in main thread to check status?
            # Or just a signal.
            pass
            
        # Re-enable buttons (unsafe from thread, but let's fix this in next step if needed)
        # For now, just let it be. 
        # Actually, let's fix it properly now.
        
        QMetaObject.invokeMethod(self.btn_run, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, True))
        QMetaObject.invokeMethod(self.btn_save, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, True))
        QMetaObject.invokeMethod(self.status_label, "setText", Qt.QueuedConnection, Q_ARG(str, "运行结束"))



class WorkflowTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.hover_row = -1

    def leaveEvent(self, event):
        self.hover_row = -1
        self.viewport().update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        item = self.itemAt(event.pos())
        old_hover = self.hover_row
        if item:
            self.hover_row = item.row()
        else:
            self.hover_row = -1
        
        if self.hover_row != old_hover:
            self.viewport().update()
        super().mouseMoveEvent(event)

class WorkflowItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.row_height = 68
        # Colors from the screenshot
        self.icon_colors = ["#409EFF", "#36C1F0", "#67C23A", "#2F9E44"]

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.row_height)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        
        # Background
        bg_rect = option.rect
        is_selected = option.state & QStyle.State_Selected
        is_hovered = False
        
        if hasattr(self.parent(), "hover_row"):
            if self.parent().hover_row == index.row():
                is_hovered = True
        
        if is_selected:
            painter.fillRect(bg_rect, QColor("#F0F7FF"))
        elif is_hovered:
            painter.fillRect(bg_rect, QColor("#F5F7FA"))
        else:
            painter.fillRect(bg_rect, QColor("#FFFFFF"))

        # Get Data
        text = str(index.data(Qt.DisplayRole) or "")
        
        if index.column() == 0:
            # Application Name Column
            icon_size = 32
            margin_left = 20
            
            # 1. Draw Icon
            icon_rect = QRect(bg_rect.left() + margin_left, 
                              bg_rect.top() + (bg_rect.height() - icon_size) // 2, 
                              icon_size, icon_size)
            
            # Color based on row
            colors = ["#409EFF", "#36C1F0", "#67C23A", "#F56C6C"]
            color = QColor(colors[index.row() % len(colors)])
            
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(icon_rect, 4, 4)
            
            if text:
                painter.setPen(Qt.white)
                font = painter.font()
                font.setBold(True)
                font.setPointSize(12)
                painter.setFont(font)
                painter.drawText(icon_rect, Qt.AlignCenter, text[0].upper())
            
            # 2. Draw Text
            text_rect = QRect(icon_rect.right() + 15, bg_rect.top(), 
                              bg_rect.width() - icon_rect.right() - 25, bg_rect.height())
            painter.setPen(QColor("#303133"))
            font = painter.font()
            font.setBold(False)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
            
        elif index.column() == 1:
            # Time Column
            painter.setPen(QColor("#909399"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            # Indent from right
            text_rect = bg_rect.adjusted(0, 0, -20, 0)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignRight, text)
            
        elif index.column() == 2:
            # Status Column
            painter.setPen(QColor("#909399"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            text_rect = bg_rect.adjusted(10, 0, -10, 0)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)

        # Bottom Border
        painter.setPen(QColor("#EBEEF5"))
        painter.drawLine(bg_rect.bottomLeft(), bg_rect.bottomRight())
        
        painter.restore()

class FlowManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ViewAuto - 流程管理")
        self.resize(1200, 800)
        self.workflow_manager = WorkflowManager()
        
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("background-color: #F5F7FA; border-right: 1px solid #E4E7ED;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(15)
        
        # Create Button
        btn_new = QPushButton("+ 新建")
        btn_new.setFixedHeight(36)
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setStyleSheet("""
            QPushButton {
                background-color: #F56C6C; 
                color: white; 
                border-radius: 18px; 
                font-size: 13px; 
                font-weight: bold;
                outline: none;
            }
            QPushButton:hover { background-color: #F78989; }
        """)
        btn_new.clicked.connect(self.create_new)
        sidebar_layout.addWidget(btn_new)
        
        # Nav Menu
        self.nav_list = QListWidget()
        self.nav_list.setFrameShape(QFrame.NoFrame)
        self.nav_list.setStyleSheet("""
            QListWidget { background-color: transparent; border: none; outline: none; }
            QListWidget::item { height: 40px; border-radius: 4px; color: #606266; padding-left: 10px; }
            QListWidget::item:hover { background-color: #E6E8EB; }
            QListWidget::item:selected { background-color: #ECF5FF; color: #409EFF; }
        """)
        items = ["我的工作流"]
        for i, label in enumerate(items):
            item = QListWidgetItem(label)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        sidebar_layout.addWidget(self.nav_list)
        sidebar_layout.addStretch()
        
        main_layout.addWidget(sidebar)
        
        # Content Area
        content = QFrame()
        content.setStyleSheet("background-color: #FFFFFF;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("我的工作流")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #303133;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Refresh & Search
        btn_refresh = QPushButton("刷新")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("border: none; color: #409EFF;")
        btn_refresh.clicked.connect(self.refresh)
        header_layout.addWidget(btn_refresh)
        
        content_layout.addLayout(header_layout)
        
        # Workflow List (Table)
        self.wf_table = WorkflowTable()
        self.wf_table.setColumnCount(3)
        self.wf_table.setHorizontalHeaderLabels(["应用名称", "更新时间", "状态"])
        
        # Table Header Styling
        header = self.wf_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self.wf_table.verticalHeader().setVisible(False)
        self.wf_table.verticalHeader().setDefaultSectionSize(68) # Force row height
        self.wf_table.setShowGrid(False)
        self.wf_table.setFrameShape(QFrame.NoFrame)
        self.wf_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.wf_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.wf_table.setSortingEnabled(True)
        self.wf_table.horizontalHeader().setSortIndicator(1, Qt.DescendingOrder)
        
        # Apply Delegate BEFORE refresh
        self.wf_table.setItemDelegate(WorkflowItemDelegate(self.wf_table))
        
        self.wf_table.setStyleSheet("""
            QTableWidget { 
                border: none; 
                background-color: white; 
                selection-background-color: #F0F7FF; 
                selection-color: #303133;
                outline: none;
            }
            QTableWidget::item { 
                border: none; 
                padding: 0px;
            }
            QHeaderView::section { 
                background-color: white; 
                border: none; 
                border-bottom: 1px solid #EBEEF5; 
                color: #909399; 
                padding: 10px 20px; 
                font-weight: normal; 
            }
        """)
        self.wf_table.cellDoubleClicked.connect(self.on_table_double_click)
        self.wf_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wf_table.customContextMenuRequested.connect(self.show_context_menu)
        
        content_layout.addWidget(self.wf_table)
        
        main_layout.addWidget(content)
        
        self.refresh()

    def refresh(self):
        # Disable sorting during data update to prevent row mismatch
        self.wf_table.setSortingEnabled(False)
        self.wf_table.setRowCount(0)
        
        workflows = self.workflow_manager.list_workflows()
        
        row = 0
        for group, names in workflows.items():
            for name in names:
                self.wf_table.insertRow(row)
                
                # Name Item
                name_item = QTableWidgetItem(name)
                name_item.setData(Qt.UserRole, {"name": name, "group": group})
                self.wf_table.setItem(row, 0, name_item)
                
                # Time Item
                time_str = "-"
                try:
                    path = os.path.join("workflows", group, f"{name}.json")
                    if os.path.exists(path):
                        mtime = os.path.getmtime(path)
                        dt = datetime.fromtimestamp(mtime)
                        time_str = get_relative_time(dt)
                except:
                    pass
                time_item = QTableWidgetItem(time_str)
                time_item.setForeground(QColor("#909399"))
                self.wf_table.setItem(row, 1, time_item)
                
                # Status Item
                status_item = QTableWidgetItem("编辑中")
                status_item.setForeground(QColor("#909399"))
                self.wf_table.setItem(row, 2, status_item)
                
                self.wf_table.setRowHeight(row, 68)
                row += 1
        
        # Re-enable sorting and apply default sort
        self.wf_table.setSortingEnabled(True)
        self.wf_table.horizontalHeader().setSortIndicator(1, Qt.DescendingOrder)

    def on_table_double_click(self, row, col):
        item = self.wf_table.item(row, 0)
        if item:
            data = item.data(Qt.UserRole)
            self.open_editor(data["name"], data["group"])

    def open_editor(self, name, group):
        rect = self.geometry()
        editor = MainWindow(manager_ref=self, initial_geometry=rect)
        editor.load_workflow(name, group)
        editor.show()
        self.hide()

    def create_new(self):
        rect = self.geometry()
        editor = MainWindow(manager_ref=self, initial_geometry=rect)
        editor.show()
        self.hide()

    def show_context_menu(self, pos):
        item = self.wf_table.itemAt(pos)
        if not item:
            return
        # Ensure we get the name item (col 0)
        row = item.row()
        name_item = self.wf_table.item(row, 0)
        if not name_item:
            return
            
        data = name_item.data(Qt.UserRole)
        name = data["name"]
        group = data["group"]
        
        menu = QMenu(self)
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        
        action = menu.exec(self.wf_table.mapToGlobal(pos))
        
        if action == edit_action:
            self.open_editor(name, group)
        elif action == delete_action:
            res = QMessageBox.question(self, "确认删除", f"确定删除流程 {name}？", QMessageBox.Yes | QMessageBox.No)
            if res == QMessageBox.Yes:
                self.workflow_manager.delete_workflow(name, group)
                self.refresh()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlowManagerWindow()
    window.show()
    sys.exit(app.exec())
