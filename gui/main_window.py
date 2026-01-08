import sys
import os
import json
import logging
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QListWidget, QTreeWidget, QTreeWidgetItem, 
                               QPushButton, QLabel, QMessageBox, QInputDialog, 
                               QMenu, QDialog, QFormLayout, QLineEdit, QComboBox, 
                               QCheckBox, QAbstractItemView, QTabWidget, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
                               QSplitter, QTextEdit, QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QScrollArea)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QRect, Slot, QObject, QMetaObject, Q_ARG, QEvent, QMimeData, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QIcon, QAction, QCursor, QDrag, QPixmap
from apscheduler.schedulers.qt import QtScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import Engine
from core.workflow_manager import WorkflowManager
from tools.basic_tools import PrintLogAction, DelayAction, SetVariableAction
from tools.web_tools import (OpenBrowserAction, CloseBrowserAction, ClickElementAction, 
                             InputTextAction, GoToUrlAction, GetTextAction,
                             HoverElementAction, SwitchFrameAction, ScrollToElementAction, SwitchWindowAction,
                             DrawMousePathAction, HttpDownloadAction)
from tools.logic_tools import (LoopAction, ForEachAction, WhileAction, 
                               IfAction, ElseIfAction, ElseAction, 
                               BreakAction, ContinueAction)
from tools.util_tools import (WaitForFileAndCopyAction, ClearDirectoryAction, OCRImageAction, WeChatNotifyAction)
from tools.excel_tools import (OpenExcelAction, ReadExcelAction, WriteExcelAction, CloseExcelAction, GetExcelRowCountAction, SaveExcelAction)

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
        "获取文本": GetTextAction,
        "悬停元素": HoverElementAction,
        "滚动到元素": ScrollToElementAction,
        "切换 iFrame": SwitchFrameAction,
        "切换窗口": SwitchWindowAction,
        "绘制鼠标轨迹": DrawMousePathAction,
        "HTTP 下载": HttpDownloadAction,
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
    def __init__(self, tool_name, schema, current_params=None, parent=None, scope_anchor=None):
        super().__init__(parent)
        self.setWindowTitle(f"配置 {tool_name}")
        self.schema = schema
        self.params = current_params or {}
        self.inputs = {}
        self.resize(480, 420)
        self.scope_anchor = scope_anchor
        tab_widget = QTabWidget()
        basic_tab = QWidget()
        advanced_tab = QWidget()
        tab_widget.addTab(basic_tab, "基本设置")
        tab_widget.addTab(advanced_tab, "高级设置")
        basic_layout = QFormLayout(basic_tab)
        advanced_layout = QFormLayout(advanced_tab)
        def make_fx_row(inp_widget):
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0,0,0,0)
            h.setSpacing(6)
            h.addWidget(inp_widget)
            fx_btn = QPushButton("fx")
            fx_btn.setFixedWidth(36)
            fx_btn.clicked.connect(lambda: self.open_variable_picker(inp_widget))
            h.addWidget(fx_btn)
            return container
        for field in schema:
            key = field['name']
            label = field.get('label', key)
            default = field.get('default', '')
            val = self.params.get(key, default)
            target_layout = basic_layout if not field.get('advanced', False) else advanced_layout
            if 'options' in field and isinstance(field['options'], list):
                inp = QComboBox()
                for opt in field['options']:
                    inp.addItem(str(opt))
                if str(val) in [str(o) for o in field['options']]:
                    inp.setCurrentText(str(val))
            elif field['type'] == 'bool':
                inp = QCheckBox()
                inp.setChecked(bool(val))
            elif field['type'] in ('int', 'float'):
                inp = QLineEdit(str(val))
            elif field['type'] in ('text',):
                inp = QTextEdit(str(val))
                inp.setFixedHeight(60)
            else:
                inp = QLineEdit(str(val))
            if isinstance(inp, (QLineEdit, QTextEdit)):
                target_layout.addRow(label + ":", make_fx_row(inp))
            else:
                target_layout.addRow(label + ":", inp)
            self.inputs[key] = (inp, field['type'])
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
    def open_variable_picker(self, target_widget):
        dlg = QDialog(self)
        dlg.setWindowTitle("选择流程变量")
        v = QVBoxLayout(dlg)
        search = QLineEdit()
        v.addWidget(search)
        lst = QListWidget()
        avail = []
        try:
            if self.parent() and hasattr(self.parent(), "gather_context_variables_scoped"):
                avail = self.parent().gather_context_variables_scoped(self.scope_anchor)
        except:
            pass
        for name in sorted(set(avail)):
            lst.addItem(name)
        v.addWidget(lst)
        hl = QHBoxLayout()
        btn_ok = QPushButton("确认")
        btn_cancel = QPushButton("取消")
        hl.addStretch()
        hl.addWidget(btn_cancel)
        hl.addWidget(btn_ok)
        v.addLayout(hl)
        def apply_selected():
            item = lst.currentItem()
            if not item:
                dlg.reject()
                return
            var = item.text()
            text = f"{{{var}}}"
            if isinstance(target_widget, QLineEdit):
                target_widget.setText(text)
            elif isinstance(target_widget, QTextEdit):
                target_widget.setPlainText(text)
            dlg.accept()
        btn_ok.clicked.connect(apply_selected)
        btn_cancel.clicked.connect(dlg.reject)
        def filter_list(t):
            lst.clear()
            for name in sorted(set(avail)):
                if t.strip().lower() in name.lower():
                    lst.addItem(name)
        search.textChanged.connect(filter_list)
        lst.itemDoubleClicked.connect(lambda _: apply_selected())
        dlg.exec()

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
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(icon_rect, Qt.AlignCenter, tool_name[0] if tool_name else "?")
        
        # Title
        title_rect = QRect(icon_rect.right() + 12, content_rect.top() + 4, content_rect.width() - 50, 20)
        font.setPointSize(10)
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
        font.setPointSize(9)
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ViewAuto - 智能自动化流程编排")
        self.resize(1400, 900)
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
        
        # Saved Workflows Tab
        self.init_saved_workflows_tab()
        
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
        
        self.btn_save = self.create_toolbar_btn("保存", "#67C23A")
        self.btn_save.clicked.connect(self.save_workflow_dialog)
        
        self.btn_run = self.create_toolbar_btn("运行", "#409EFF")
        self.btn_run.clicked.connect(self.run_workflow)

        self.btn_schedule = self.create_toolbar_btn("定时 (9:00)", "#E6A23C")
        self.btn_schedule.clicked.connect(self.toggle_schedule)
        
        self.btn_clear = self.create_toolbar_btn("清空", "#F56C6C")
        self.btn_clear.clicked.connect(self.confirm_clear_workflow)
        
        self.btn_undo = self.create_toolbar_btn("撤销", "#909399")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.perform_undo)
        
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
        self.workflow_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.workflow_tree.tool_dropped.connect(self.handle_tool_drop)
        self.workflow_tree.internal_move.connect(self.handle_internal_move)
        self.workflow_tree.setItemDelegate(StepItemDelegate(self.workflow_tree))
        self.workflow_tree.setUniformRowHeights(False)
        self.workflow_tree.setStyleSheet("QTreeWidget { border: none; }")
        self.workflow_tree.itemCollapsed.connect(self.handle_item_collapsed)
        self.workflow_tree.itemExpanded.connect(self.handle_item_expanded)
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
            p = d.get("params", {}) or {}
            for k, v in p.items():
                if isinstance(v, str) and (k.endswith("output_variable") or k.endswith("_variable") or k in ("output_variable","driver_variable","item_variable","list_variable")):
                    into.add(v)
        vars_set = set()
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
                    add_vars_from_item(it, vars_set)
                    for j in range(it.childCount()):
                        sub = it.child(j)
                        if not is_end_marker(sub):
                            add_vars_from_item(sub, vars_set)
                            if traverse(sub):
                                return True
                    return True
                add_vars_from_item(it, vars_set)
                if traverse(it):
                    return True
            return False
        traverse(root)
        if within_loop_children():
            vars_set.add("loop_index")
        return sorted(vars_set)

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
                QMessageBox.information(self, "成功", f"流程 {name} 保存成功！")
                self.refresh_saved_workflows_list()
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
            self.workflow_tree.clear()
            self.load_workflow_to_tree(workflow_data)
            self.status_label.setText(f"已加载流程: {group}/{name}")

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
        # Normalize indicator to enum
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
        # Normalize indicator to enum
        try:
            if isinstance(indicator, int):
                indicator = QAbstractItemView.DropIndicatorPosition(indicator)
        except Exception:
            pass

        # 1. EndMarker Logic (Target Adjustment)
        if target_item:
            data = target_item.data(0, Qt.UserRole)
            if data and data.get("tool_name") == "EndMarker":
                if indicator == QAbstractItemView.BelowItem:
                    # Drop below EndMarker -> Insert after the block
                    pass
                else:
                    # Drop on or above EndMarker -> Insert inside loop (Append to logic tool children)
                    parent = target_item.parent()
                    index = parent.indexOfChild(target_item) if parent else self.workflow_tree.indexOfTopLevelItem(target_item)
                    
                    # Find previous sibling (The Logic Tool)
                    logic_tool = None
                    if index > 0:
                        if parent:
                            logic_tool = parent.child(index - 1)
                        else:
                            logic_tool = self.workflow_tree.topLevelItem(index - 1)
                    
                    if logic_tool:
                        target_item = logic_tool
                        indicator = QAbstractItemView.OnItem # Append to children

        # NEW: Treat OnItem drops on non-container tools as Insert Below
        if target_item and indicator == QAbstractItemView.OnItem:
            t_data = target_item.data(0, Qt.UserRole)
            t_name = t_data.get("tool_name") if t_data else None
            if t_name and t_name not in LOGIC_TOOLS:
                indicator = QAbstractItemView.BelowItem

        # 2. Check if moving item is Logic Tool with EndMarker
        end_marker_to_move = None
        item_data = item.data(0, Qt.UserRole)
        if item_data and item_data.get("tool_name") in LOGIC_TOOLS:
            # Find its sibling EndMarker
            parent = item.parent()
            index = parent.indexOfChild(item) if parent else self.workflow_tree.indexOfTopLevelItem(item)
            
            # Check next sibling
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

        # 3. Perform Move
        # Remove item from current parent
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
            
        # Add to new location
        if target_item:
            parent = target_item.parent()
            if indicator == QAbstractItemView.OnItem:
                # Append as child
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
            
        # Normalize indicator to enum for reliable comparisons
        try:
            if isinstance(indicator, int):
                indicator = QAbstractItemView.DropIndicatorPosition(indicator)
        except Exception:
            pass
        
        schema = tool_cls().get_param_schema()
        params = existing_params or {}
        
        if schema and existing_params is None:
            dlg = ParameterDialog(tool_name, schema, parent=self, scope_anchor=('add', target_item, indicator))
            if dlg.exec():
                params = dlg.get_params()
            else:
                return 

        # Handle EndMarker target adjustment
        if target_item:
            data = target_item.data(0, Qt.UserRole)
            if data and data.get("tool_name") == "EndMarker":
                if indicator == QAbstractItemView.BelowItem:
                    # Drop below EndMarker -> Insert after the block
                    pass
                else:
                    # Drop on or above EndMarker -> Insert inside loop (Append to logic tool children)
                    parent = target_item.parent()
                    index = parent.indexOfChild(target_item) if parent else self.workflow_tree.indexOfTopLevelItem(target_item)
                    
                    # Find previous sibling (The Logic Tool)
                    logic_tool = None
                    if index > 0:
                        if parent:
                            logic_tool = parent.child(index - 1)
                        else:
                            logic_tool = self.workflow_tree.topLevelItem(index - 1)
                    
                    if logic_tool:
                        target_item = logic_tool
                        indicator = QAbstractItemView.OnItem # Append to children

        # NEW: Treat OnItem drops on non-container tools as Insert Below
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
                # Append as child
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

        # Add EndMarker if logic tool
        if tool_name in LOGIC_TOOLS:
            end_item = QTreeWidgetItem([f"结束 {tool_name}"])
            end_item.setData(0, Qt.UserRole, {"tool_name": "EndMarker", "params": {}})
            end_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable) # Disable drag
            
            # Insert EndMarker as Sibling (After item)
            parent = item.parent()
            if parent:
                index = parent.indexOfChild(item)
                parent.insertChild(index + 1, end_item)
            else:
                index = self.workflow_tree.indexOfTopLevelItem(item)
                self.workflow_tree.insertTopLevelItem(index + 1, end_item)
            
            item.setExpanded(True)
        
        # Snapshot for undo
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
            # If deleting a logic tool, also remove its sibling EndMarker
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
                    # Check next top-level for EndMarker
                    if idx + 1 < self.workflow_tree.topLevelItemCount():
                        sib = self.workflow_tree.topLevelItem(idx + 1)
                        sdata = sib.data(0, Qt.UserRole) or {}
                        if sdata.get("tool_name") == "EndMarker":
                            # Remove EndMarker first to avoid index shift
                            em_idx = self.workflow_tree.indexOfTopLevelItem(sib)
                            if em_idx != -1:
                                self.workflow_tree.takeTopLevelItem(em_idx)
                idx = self.workflow_tree.indexOfTopLevelItem(item)
                if idx != -1:
                    self.workflow_tree.takeTopLevelItem(idx)
        elif action == toggle_disable_action:
            self.create_undo_snapshot()
            # Toggle disabled flag
            d = item.data(0, Qt.UserRole) or {}
            d["disabled"] = not d.get("disabled", False)
            item.setData(0, Qt.UserRole, d)
            # Refresh view
            self.workflow_tree.viewport().update()

    def edit_step(self, item):
        data = item.data(0, Qt.UserRole)
        tool_name = data["tool_name"]
        params = data["params"]
        
        tool_cls = ENGINE_REGISTRY.get(tool_name)
        schema = tool_cls().get_param_schema()
        
        if schema:
            dlg = ParameterDialog(tool_name, schema, current_params=params, parent=self, scope_anchor=('edit', item))
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
        # Find sibling EndMarker and hide it
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
        # Find sibling EndMarker and show it
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
