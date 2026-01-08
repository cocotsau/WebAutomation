import sys
import os
import json
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QListWidget, QTreeWidget, QTreeWidgetItem, 
                               QPushButton, QLabel, QMessageBox, QInputDialog, 
                               QMenu, QDialog, QFormLayout, QLineEdit, QComboBox, 
                               QCheckBox, QAbstractItemView, QTabWidget, QStyledItemDelegate, QStyle, QStyleOptionViewItem)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
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
from tools.logic_tools import LoopAction, ForEachAction, WhileAction
from tools.util_tools import (WaitForFileAndCopyAction, ClearDirectoryAction, OCRImageAction, WeChatNotifyAction)
from tools.excel_tools import (OpenExcelAction, ReadExcelAction, WriteExcelAction, CloseExcelAction)

# Categorized Registry
TOOL_CATEGORIES = {
    "基础工具": {
        "打印日志": PrintLogAction,
        "延时": DelayAction,
        "设置变量": SetVariableAction
    },
    "Web 自动化": {
        "打开浏览器": OpenBrowserAction,
        "跳转链接": GoToUrlAction,
        "点击元素": ClickElementAction,
        "输入文本": InputTextAction,
        "获取文本": GetTextAction,
        "悬停元素": HoverElementAction,
        "滚动到元素": ScrollToElementAction,
        "切换 Frame": SwitchFrameAction,
        "切换窗口": SwitchWindowAction,
        "绘制鼠标轨迹": DrawMousePathAction,
        "HTTP 下载": HttpDownloadAction,
        "关闭浏览器": CloseBrowserAction
    },
    "Excel 工具": {
        "打开 Excel": OpenExcelAction,
        "读取 Excel": ReadExcelAction,
        "写入 Excel": WriteExcelAction,
        "关闭 Excel": CloseExcelAction
    },
    "逻辑控制": {
        "For循环": LoopAction,
        "Foreach循环": ForEachAction,
        "While循环": WhileAction
    },
    "数据与工具": {
        "等待并复制文件": WaitForFileAndCopyAction,
        "清空文件夹": ClearDirectoryAction,
        "OCR 文字识别": OCRImageAction,
        "企业微信通知": WeChatNotifyAction
    }
}

# Flattened Registry for Engine
ENGINE_REGISTRY = {}
for cat, tools in TOOL_CATEGORIES.items():
    ENGINE_REGISTRY.update(tools)

class ParameterDialog(QDialog):
    def __init__(self, tool_name, schema, current_params=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"配置 {tool_name}")
        self.schema = schema
        self.params = current_params or {}
        self.inputs = {}
        self.resize(400, 300)
        
        layout = QFormLayout(self)
        
        for field in schema:
            key = field['name']
            label = field['label']
            default = field.get('default', '')
            val = self.params.get(key, default)
            
            if field['type'] == 'bool':
                inp = QCheckBox()
                inp.setChecked(bool(val))
            elif field['type'] == 'int' or field['type'] == 'float':
                inp = QLineEdit(str(val))
            else:
                inp = QLineEdit(str(val))
                
            layout.addRow(label, inp)
            self.inputs[key] = (inp, field['type'])
            
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def get_params(self):
        result = {}
        for key, (inp, type_str) in self.inputs.items():
            if type_str == 'bool':
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
            else:
                result[key] = inp.text()
        return result

class WorkflowTreeWidget(QTreeWidget):
    tool_dropped = Signal(str, object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def dragEnterEvent(self, event):
        if event.source() == self:
            super().dragEnterEvent(event)
        elif isinstance(event.source(), QTreeWidget):
            # Call super to let QAbstractItemView handle state
            super().dragEnterEvent(event)
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() == self:
            super().dragMoveEvent(event)
        elif isinstance(event.source(), QTreeWidget):
            # Call super to update drop indicator
            super().dragMoveEvent(event)
            # Force CopyAction
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.source() == self:
            super().dropEvent(event)
        elif isinstance(event.source(), QTreeWidget):
            item = event.source().currentItem()
            # Ensure it is a tool (has parent)
            if item.parent() is None:
                event.ignore()
                return
            
            tool_name = item.text(0)
            target = self.itemAt(event.pos())
            indicator = self.dropIndicatorPosition()
            
            self.tool_dropped.emit(tool_name, target, indicator)
            event.acceptProposedAction()

class StepItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.row_height = 56
        self.margin_v = 10
        self.margin_h = 12
        self.radius = 10

    def sizeHint(self, option, index):
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(base.height(), self.row_height + self.margin_v))

    def paint(self, painter, option, index):
        # Prepare style option and derive text rect so we don't cover branch indicators
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        # Compute text area rect from style, then add our padding
        view = self.parent()
        text_rect = view.style().subElementRect(QStyle.SE_ItemViewItemText, opt, view)
        bg_rect = text_rect.adjusted(self.margin_h, self.margin_v // 2, -self.margin_h, -self.margin_v // 2)

        # Card background
        selected = bool(option.state & QStyle.State_Selected)
        base_color = QColor("#F7F9FC") if not selected else QColor("#E8F0FE")
        border_color = QColor("#E5EAF0") if not selected else QColor("#8AB4F8")
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QBrush(base_color))
        painter.drawRoundedRect(bg_rect, self.radius, self.radius)

        # Extract tool name and params from UserRole
        data = index.data(Qt.UserRole) or {}
        tool_name = str(data.get("tool_name", index.data(Qt.DisplayRole) or ""))
        params = data.get("params", {})
        params_text = str(params)

        # Layout: title and subtitle
        title_rect = bg_rect.adjusted(12, 8, -12, -26)
        subtitle_rect = bg_rect.adjusted(12, 28, -12, -8)

        # Draw title (tool name) bold
        title_font = option.font
        title_font.setPointSize(title_font.pointSize() + 1)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#111827"))
        # Elide title if too long
        fm_title = painter.fontMetrics()
        elided_title = fm_title.elidedText(tool_name, Qt.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignVCenter | Qt.TextSingleLine, elided_title)

        # Draw subtitle (params) smaller and elided
        subtitle_font = option.font
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#4B5563"))
        fm_sub = painter.fontMetrics()
        elided_params = fm_sub.elidedText(params_text, Qt.ElideRight, subtitle_rect.width())
        painter.drawText(subtitle_rect, Qt.AlignVCenter | Qt.TextSingleLine, elided_params)

        painter.restore()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ViewAuto - 自动化工具")
        self.resize(1300, 850)
        
        # Managers
        self.workflow_manager = WorkflowManager()
        self.engine = Engine()

        # Scheduler
        self.scheduler = QtScheduler()
        self.scheduler.start()
        
        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left Panel: Tab Widget (Toolbox & Saved Workflows)
        self.left_tabs = QTabWidget()
        
        # Tab 1: Toolbox
        toolbox_widget = QWidget()
        toolbox_layout = QVBoxLayout(toolbox_widget)
        toolbox_layout.addWidget(QLabel("<b>工具箱</b> (双击添加)"))
        
        self.toolbox_tree = QTreeWidget()
        self.toolbox_tree.setHeaderLabel("可用工具")
        self.toolbox_tree.setDragEnabled(True)
        self.toolbox_tree.setDragDropMode(QAbstractItemView.DragOnly)
        self.toolbox_tree.itemDoubleClicked.connect(self.add_tool_to_workflow)
        
        # Populate Toolbox
        for category, tools in TOOL_CATEGORIES.items():
            cat_item = QTreeWidgetItem([category])
            # Disable selection and dragging for categories
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsDragEnabled)
            
            for tool_name in tools.keys():
                tool_item = QTreeWidgetItem([tool_name])
                tool_item.setData(0, Qt.UserRole, "tool")
                # Ensure tools are draggable
                tool_item.setFlags(tool_item.flags() | Qt.ItemIsDragEnabled)
                cat_item.addChild(tool_item)
            
            self.toolbox_tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)
            
        toolbox_layout.addWidget(self.toolbox_tree)
        self.left_tabs.addTab(toolbox_widget, "工具箱")
        
        # Tab 2: Saved Workflows
        self.init_saved_workflows_tab()
        
        main_layout.addWidget(self.left_tabs, 1)
        
        # Right Panel: Workflow Editor (Tree)
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("<b>流程步骤</b> (拖拽排序/嵌套，右键编辑)"))
        
        self.workflow_tree = WorkflowTreeWidget()
        self.workflow_tree.setHeaderLabel("步骤")
        # self.workflow_tree.setDragDropMode(QAbstractItemView.InternalMove) # Handled in class
        # self.workflow_tree.setDefaultDropAction(Qt.MoveAction)
        self.workflow_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.workflow_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.workflow_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.workflow_tree.tool_dropped.connect(self.handle_tool_drop)
        self.workflow_tree.setItemDelegate(StepItemDelegate(self.workflow_tree))
        self.workflow_tree.setUniformRowHeights(False)
        self.workflow_tree.setStyleSheet("QTreeView { outline: none; } QTreeView::item:selected { background: transparent; }")
        
        right_layout.addWidget(self.workflow_tree)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("保存流程")
        self.btn_save.clicked.connect(self.save_workflow_dialog)
        
        self.btn_run = QPushButton("立即运行")
        self.btn_run.clicked.connect(self.run_workflow)
        
        self.btn_schedule = QPushButton("定时运行 (9:00 AM)")
        self.btn_schedule.clicked.connect(self.toggle_schedule)
        
        self.btn_clear = QPushButton("清空步骤")
        self.btn_clear.clicked.connect(self.confirm_clear_workflow)
        self.btn_undo = QPushButton("撤销操作")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.perform_undo)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_schedule)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_undo)
        right_layout.addLayout(btn_layout)
        
        # Status Bar
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label)
        
        main_layout.addLayout(right_layout, 2)

    def create_undo_snapshot(self):
        self.undo_snapshot = self.get_workflow_data()
        self.btn_undo.setEnabled(True)

    def perform_undo(self):
        snapshot = getattr(self, "undo_snapshot", None)
        if not snapshot:
            QMessageBox.information(self, "提示", "没有可撤销的内容。")
            return
        
        # Save current state as redo? (Optional, but let's stick to simple undo for now)
        # Or better, just restore.
        
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
        text, ok = QInputDialog.getText(self, "二次确认", "请输入“清空”以继续：")
        if not ok or text.strip() != "清空":
            QMessageBox.information(self, "已取消", "未通过二次确认，已取消清空。")
            return
            
        self.create_undo_snapshot()
        self.workflow_tree.clear()
        self.status_label.setText("已清空，可撤销。")
    def init_saved_workflows_tab(self):
        self.saved_tab = QWidget()
        layout = QVBoxLayout(self.saved_tab)
        
        layout.addWidget(QLabel("<b>已保存流程</b> (双击加载，右键管理)"))
        
        self.saved_workflows_tree = QTreeWidget()
        self.saved_workflows_tree.setHeaderLabel("流程列表")
        self.saved_workflows_tree.itemDoubleClicked.connect(self.load_saved_workflow_item)
        self.saved_workflows_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.saved_workflows_tree.customContextMenuRequested.connect(self.show_saved_workflows_context_menu)
        
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

        # Dialog to get name and group
        dlg = QDialog(self)
        dlg.setWindowTitle("保存流程")
        layout = QFormLayout(dlg)
        
        name_edit = QLineEdit()
        group_edit = QComboBox()
        group_edit.setEditable(True)
        
        # Populate existing groups
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
                QMessageBox.information(self, "成功", f"流程 '{name}' 已保存到分组 '{group}'。")
                self.refresh_saved_workflows_list()
            else:
                QMessageBox.critical(self, "错误", "保存失败，请检查日志。")

    def load_saved_workflow_item(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "workflow":
            self.load_saved_workflow(data["name"], data["group"])

    def show_saved_workflows_context_menu(self, pos):
        item = self.saved_workflows_tree.itemAt(pos)
        if not item:
            return
            
        data = item.data(0, Qt.UserRole)
        if not data:
            return
            
        menu = QMenu()
        
        if data["type"] == "workflow":
            load_action = menu.addAction("加载到编辑区")
            run_action = menu.addAction("直接运行")
            delete_action = menu.addAction("删除")
            
            action = menu.exec(self.saved_workflows_tree.mapToGlobal(pos))
            
            if action == load_action:
                self.load_saved_workflow(data["name"], data["group"])
            elif action == run_action:
                self.run_saved_workflow(data["name"], data["group"])
            elif action == delete_action:
                self.delete_saved_workflow(data["name"], data["group"])
        
        elif data["type"] == "group":
            # Group actions if needed (e.g., delete entire group)
            pass

    def load_saved_workflow(self, name, group):
        data = self.workflow_manager.load_workflow(name, group)
        if data:
            self.workflow_tree.clear()
            self.load_workflow_to_tree(data)
            QMessageBox.information(self, "加载成功", f"流程 '{name}' 已加载。")
        else:
            QMessageBox.warning(self, "加载失败", "无法加载流程数据。")

    def run_saved_workflow(self, name, group):
        data = self.workflow_manager.load_workflow(name, group)
        if not data:
             QMessageBox.warning(self, "错误", "无法加载流程数据。")
             return
             
        self.status_label.setText(f"正在运行: {name}...")
        QApplication.processEvents()
        
        try:
            # Create a temporary engine or use existing one?
            # Using existing one is safer for resource management, but blocks UI.
            self.engine.load_workflow(data, ENGINE_REGISTRY)
            self.engine.run()
            self.status_label.setText(f"流程 '{name}' 运行完成。")
            QMessageBox.information(self, "成功", f"流程 '{name}' 运行完成！")
        except Exception as e:
            self.status_label.setText(f"错误: {e}")
            QMessageBox.critical(self, "错误", f"流程运行失败: {str(e)}")

    def delete_saved_workflow(self, name, group):
        confirm = QMessageBox.question(self, "确认删除", f"确定要删除流程 '{name}' 吗？", 
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            if self.workflow_manager.delete_workflow(name, group):
                self.refresh_saved_workflows_list()
            else:
                QMessageBox.critical(self, "错误", "删除失败。")

    def load_workflow_to_tree(self, workflow_data, parent_item=None):
        for step in workflow_data:
            tool_name = step["tool_name"]
            params = step["params"]
            
            # Extract children if any
            children = params.pop("children", None)
            
            tree_item = QTreeWidgetItem([f"{tool_name}: {params}"])
            tree_item.setFlags(tree_item.flags() | Qt.ItemIsDropEnabled)
            # Put params back into data (without children for display/storage consistency, 
            # though children are stored in params in get_workflow_data, 
            # but when loaded we need to handle them recursively)
            
            # Wait, get_workflow_data puts children IN params.
            # So when loading, we should pop children before setting data, 
            # OR just store them. 
            # The current structure expects children to be handled by the tree structure, not the data param.
            
            tree_item.setData(0, Qt.UserRole, {"tool_name": tool_name, "params": params})
            
            if parent_item:
                parent_item.addChild(tree_item)
                parent_item.setExpanded(True)
            else:
                self.workflow_tree.addTopLevelItem(tree_item)
                
            if children:
                self.load_workflow_to_tree(children, tree_item)

    def handle_tool_drop(self, tool_name, target_item, indicator):
        # 1. Get Params
        action_class = ENGINE_REGISTRY.get(tool_name)
        if not action_class:
            return
            
        params = {}
        action_instance = action_class()
        schema = action_instance.get_param_schema()
        if schema:
            dlg = ParameterDialog(tool_name, schema, parent=self)
            if dlg.exec():
                params = dlg.get_params()
            else:
                return # Cancelled
        
        # 2. Create Item
        tree_item = QTreeWidgetItem([f"{tool_name}: {params}"])
        tree_item.setData(0, Qt.UserRole, {"tool_name": tool_name, "params": params})
        tree_item.setFlags(tree_item.flags() | Qt.ItemIsDropEnabled)
        
        # 3. Insert Item
        if not target_item:
            self.workflow_tree.addTopLevelItem(tree_item)
            return

        if indicator == QAbstractItemView.OnViewport:
             self.workflow_tree.addTopLevelItem(tree_item)
             return
             
        if indicator == QAbstractItemView.OnItem:
            target_data = target_item.data(0, Qt.UserRole)
            target_name = target_data.get("tool_name")
            if target_name in ["For循环", "Foreach循环", "While循环"]:
                target_item.addChild(tree_item)
                target_item.setExpanded(True)
            else:
                parent = target_item.parent()
                if parent:
                    idx = parent.indexOfChild(target_item)
                    parent.insertChild(idx + 1, tree_item)
                else:
                    idx = self.workflow_tree.indexOfTopLevelItem(target_item)
                    self.workflow_tree.insertTopLevelItem(idx + 1, tree_item)
        
        elif indicator == QAbstractItemView.AboveItem:
            parent = target_item.parent()
            if parent:
                idx = parent.indexOfChild(target_item)
                parent.insertChild(idx, tree_item)
            else:
                idx = self.workflow_tree.indexOfTopLevelItem(target_item)
                self.workflow_tree.insertTopLevelItem(idx, tree_item)
                
        elif indicator == QAbstractItemView.BelowItem:
            parent = target_item.parent()
            if parent:
                idx = parent.indexOfChild(target_item)
                parent.insertChild(idx + 1, tree_item)
            else:
                idx = self.workflow_tree.indexOfTopLevelItem(target_item)
                self.workflow_tree.insertTopLevelItem(idx + 1, tree_item)

    def add_tool_to_workflow(self, item, column):
        # Only add if it's a tool (has parent)
        if item.childCount() > 0 or item.parent() is None:
            return # It's a category
            
        tool_name = item.text(0)
        self.add_step(tool_name)

    def add_step(self, tool_name, params=None):
        action_class = ENGINE_REGISTRY.get(tool_name)
        if not action_class:
            return

        if params is None:
            action_instance = action_class()
            schema = action_instance.get_param_schema()
            if schema:
                dlg = ParameterDialog(tool_name, schema, parent=self)
                if dlg.exec():
                    params = dlg.get_params()
                else:
                    return 
            else:
                params = {}

        # Create Tree Item
        tree_item = QTreeWidgetItem([f"{tool_name}: {params}"])
        tree_item.setData(0, Qt.UserRole, {"tool_name": tool_name, "params": params})
        tree_item.setFlags(tree_item.flags() | Qt.ItemIsDropEnabled)
        
        # Determine where to add
        selected_items = self.workflow_tree.selectedItems()
        if selected_items:
            parent = selected_items[0]
            # Check if parent is a container type (Loop, While, ForEach)
            # For simplicity, we assume if it's in logic tools, it's a container
            parent_data = parent.data(0, Qt.UserRole)
            parent_name = parent_data.get("tool_name")
            if parent_name in ["For循环", "Foreach循环", "While循环"]:
                parent.addChild(tree_item)
                parent.setExpanded(True)
            else:
                # Add as sibling after
                parent_parent = parent.parent()
                if parent_parent:
                    index = parent_parent.indexOfChild(parent)
                    parent_parent.insertChild(index + 1, tree_item)
                else:
                    index = self.workflow_tree.indexOfTopLevelItem(parent)
                    self.workflow_tree.insertTopLevelItem(index + 1, tree_item)
        else:
            self.workflow_tree.addTopLevelItem(tree_item)

    def show_context_menu(self, pos):
        item = self.workflow_tree.itemAt(pos)
        if not item:
            return
            
        menu = QMenu()
        edit_action = menu.addAction("编辑参数")
        delete_action = menu.addAction("删除步骤")
        
        action = menu.exec(self.workflow_tree.mapToGlobal(pos))
        
        if action == delete_action:
            self.create_undo_snapshot()
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                index = self.workflow_tree.indexOfTopLevelItem(item)
                self.workflow_tree.takeTopLevelItem(index)
            self.status_label.setText("已删除步骤，可撤销。")
        elif action == edit_action:
            self.edit_step(item)

    def edit_step(self, item):
        data = item.data(0, Qt.UserRole)
        tool_name = data["tool_name"]
        current_params = data["params"]
        
        action_class = ENGINE_REGISTRY.get(tool_name)
        if not action_class:
            return
            
        action_instance = action_class()
        schema = action_instance.get_param_schema()
        
        if schema:
            dlg = ParameterDialog(tool_name, schema, current_params, parent=self)
            if dlg.exec():
                new_params = dlg.get_params()
                data["params"] = new_params
                item.setData(0, Qt.UserRole, data)
                item.setText(0, f"{tool_name}: {new_params}")

    def get_workflow_data(self):
        return self._get_items_recursive(self.workflow_tree.invisibleRootItem())

    def _get_items_recursive(self, parent_item):
        steps = []
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            data = child.data(0, Qt.UserRole)
            
            # Deep copy params to avoid modifying the UI data directly
            step_data = {
                "tool_name": data["tool_name"],
                "params": data["params"].copy()
            }
            
            # Recursively get children steps
            children_steps = self._get_items_recursive(child)
            if children_steps:
                step_data["params"]["children"] = children_steps
                
            steps.append(step_data)
        return steps

    def run_workflow(self):
        workflow_data = self.get_workflow_data()
        if not workflow_data:
            QMessageBox.warning(self, "警告", "流程为空！")
            return
            
        self.status_label.setText("运行中...")
        QApplication.processEvents()
        
        try:
            self.engine.load_workflow(workflow_data, ENGINE_REGISTRY)
            self.engine.run()
            self.status_label.setText("运行完成。")
            QMessageBox.information(self, "成功", "流程运行完成！")
        except Exception as e:
            self.status_label.setText(f"错误: {e}")
            QMessageBox.critical(self, "错误", f"流程运行失败: {str(e)}")

    def toggle_schedule(self):
        job_id = "daily_workflow"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            self.btn_schedule.setText("定时运行 (9:00 AM)")
            self.status_label.setText("定时任务已取消。")
        else:
            workflow_data = self.get_workflow_data()
            if not workflow_data:
                 QMessageBox.warning(self, "警告", "无法定时空流程！")
                 return

            def scheduled_job():
                print(f"[{datetime.now()}] 运行定时流程...")
                eng = Engine()
                eng.load_workflow(workflow_data, ENGINE_REGISTRY)
                eng.run()
            
            trigger = CronTrigger(hour=9, minute=0, second=0)
            
            self.scheduler.add_job(scheduled_job, trigger, id=job_id)
            self.btn_schedule.setText("已定时 (点击取消)")
            self.status_label.setText("流程已定时于每天 9:00 AM 运行。")
            
            QMessageBox.information(self, "已定时", "流程已设置为每天上午 9:00 运行。\n\n注意：请保持软件开启。")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
