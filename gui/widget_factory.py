from PySide6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, 
                               QLineEdit, QComboBox, QCheckBox, QTextEdit, 
                               QFileDialog, QDialog, QListWidget, QListWidgetItem,
                               QVBoxLayout)
from PySide6.QtCore import Qt

class WidgetFactory:
    @staticmethod
    def create_widget(field, current_value, parent_dialog, context_getter=None, tool_name=""):
        """
        根据字段定义创建对应的控件
        :param field: 字段schema定义
        :param current_value: 当前值
        :param parent_dialog: 父级对话框(用于弹窗)
        :param context_getter: 获取上下文变量的回调函数
        :param tool_name: 当前工具名称(用于特殊逻辑判断)
        :return: (widget, value_getter_func)
        """
        key = field['name']
        label = field.get('label', key)
        default = field.get('default', '')
        val = current_value if current_value is not None else default
        
        widget = None
        
        # 1. 变量选择控件逻辑
        # Exclude output_variable for Open Browser/Open Excel (creation vs selection)
        is_creation = (key == "output_variable" and tool_name in ["打开浏览器", "打开 Excel"])
        
        if (key in ['driver_variable', 'output_variable'] or field.get('is_variable', False)) and not is_creation:
            widget = QComboBox()
            widget.setEditable(True)
            avail = {}
            if context_getter:
                try:
                    avail = context_getter()
                except:
                    pass
            
            if isinstance(avail, (list, set, tuple)):
                avail = {k: "未知" for k in avail}
            
            # Determine preferred type
            preferred_type = None
            if key == "driver_variable": preferred_type = "网页对象"
            elif key == "output_variable" and "Browser" in tool_name: preferred_type = "网页对象"
            elif key == "output_variable" and "Excel" in tool_name: preferred_type = "Excel对象"
            
            # Sort variables
            def sort_key(item):
                name, vtype = item
                prio = 0 if vtype == preferred_type else 1
                return (prio, vtype, name)
            
            sorted_vars = sorted(avail.items(), key=sort_key)
            
            for name, vtype in sorted_vars:
                widget.addItem(name, vtype)
                widget.setItemData(widget.count()-1, f"类型: {vtype}", Qt.ToolTipRole)
            
            if "Web Page" not in avail:
                widget.addItem("Web Page")
            
            # Smart Default Selection
            current_text = str(val)
            if key == 'driver_variable' and not current_text:
                 candidates = [n for n, t in avail.items() if t == "网页对象"]
                 if candidates:
                     current_text = sorted(candidates)[0]
                 else:
                     # Fallback
                     candidates = [n for n, t in avail.items() if t not in ("循环变量", "循环项")]
                     if candidates:
                         current_text = sorted(candidates)[0]

            widget.setCurrentText(current_text)
            
        # 2. 下拉选项控件
        elif 'options' in field and isinstance(field['options'], list):
            widget = QComboBox()
            for opt in field['options']:
                widget.addItem(str(opt))
            if str(val) in [str(o) for o in field['options']]:
                widget.setCurrentText(str(val))
                
        # 3. 布尔/复选框控件
        elif field['type'] == 'bool':
            widget = QCheckBox()
            widget.setChecked(bool(val))
            
        # 4. 多行文本控件
        elif field['type'] in ('text',):
            widget = QTextEdit(str(val))
            widget.setFixedHeight(60)
            
        # 5. 默认单行文本控件
        else:
            widget = QLineEdit(str(val))
            
        return widget

    @staticmethod
    def wrap_with_tools(widget, field, parent_dialog, variable_picker_callback=None, extra_context=None):
        """
        为控件添加浏览按钮和变量选择按钮
        """
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0,0,0,0)
        h.setSpacing(6)
        h.addWidget(widget)
        
        # Handle browse button
        if field:
            ui_opts = field.get("ui_options", {})
            browse_type = ui_opts.get("browse_type")
            if browse_type:
                browse_btn = QPushButton("...")
                browse_btn.setFixedWidth(30)
                browse_btn.setToolTip("选择文件/目录")
                def on_browse():
                    if browse_type == "file":
                        f_filter = ui_opts.get("file_filter", "All Files (*.*)")
                        path, _ = QFileDialog.getOpenFileName(parent_dialog, "选择文件", "", f_filter)
                        if path:
                            if isinstance(widget, QLineEdit): widget.setText(path)
                    elif browse_type == "directory":
                        path = QFileDialog.getExistingDirectory(parent_dialog, "选择目录")
                        if path:
                            if isinstance(widget, QLineEdit): widget.setText(path)
                browse_btn.clicked.connect(on_browse)
                h.addWidget(browse_btn)

        # Handle FX button (Variable Picker)
        # Only for text-input capable widgets
        if isinstance(widget, (QLineEdit, QTextEdit, QComboBox)):
             fx_btn = QPushButton("fx")
             fx_btn.setFixedWidth(36)
             if variable_picker_callback:
                 fx_btn.clicked.connect(lambda: variable_picker_callback(widget))
             h.addWidget(fx_btn)

        ui_opts = field.get("ui_options", {}) if field else {}
        if ui_opts.get("element_picker") and isinstance(widget, (QLineEdit, QTextEdit, QComboBox)):
            el_btn = QPushButton("el")
            el_btn.setFixedWidth(36)
            el_btn.clicked.connect(lambda: WidgetFactory.open_element_picker(parent_dialog, widget, extra_context))
            h.addWidget(el_btn)
             
        return container

    @staticmethod
    def open_variable_picker(parent_dialog, target_widget, context_getter=None):
        dlg = QDialog(parent_dialog)
        dlg.setWindowTitle("选择流程变量")
        v = QVBoxLayout(dlg)
        search = QLineEdit()
        search.setPlaceholderText("搜索变量...")
        v.addWidget(search)
        lst = QListWidget()
        
        avail = {}
        if context_getter:
            try:
                avail = context_getter()
            except:
                pass
        if isinstance(avail, (list, set, tuple)):
            avail = {k: "未知" for k in avail}

        def populate_list(filter_text=""):
            lst.clear()
            sorted_vars = sorted(avail.items(), key=lambda x: (x[1], x[0]))
            for name, vtype in sorted_vars:
                if filter_text.lower() in name.lower():
                    item = QListWidgetItem(f"{name}  [{vtype}]")
                    item.setData(Qt.UserRole, name)
                    lst.addItem(item)
        
        populate_list()
        
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
            var = item.data(Qt.UserRole)
            text = f"{{{var}}}"
            
            if isinstance(target_widget, QLineEdit):
                target_widget.setText(text)
            elif isinstance(target_widget, QTextEdit):
                target_widget.setPlainText(text)
            elif isinstance(target_widget, QComboBox):
                target_widget.setEditText(text)
            dlg.accept()
            
        btn_ok.clicked.connect(apply_selected)
        btn_cancel.clicked.connect(dlg.reject)
        
        def filter_list(t):
            populate_list(t)
        search.textChanged.connect(filter_list)
        lst.itemDoubleClicked.connect(lambda _: apply_selected())
        dlg.exec()

    @staticmethod
    def open_element_picker(parent_dialog, target_widget, extra_context=None):
        from PySide6.QtWidgets import QTabWidget, QMessageBox, QFormLayout
        
        # 1. 获取 managers
        private_mgr = extra_context.get("element_manager_private") if extra_context else None
        global_mgr = extra_context.get("element_manager_global") if extra_context else None
        
        # Fallback if not provided (compatibility)
        if not private_mgr and not global_mgr:
            try:
                from core.element_manager import ElementManager
                global_mgr = ElementManager("elements.json")
            except:
                pass

        dlg = QDialog(parent_dialog)
        dlg.setWindowTitle("选择元素库")
        dlg.resize(600, 500)
        
        main_layout = QVBoxLayout(dlg)
        tab_widget = QTabWidget()
        
        # Keep references to refresh functions
        refresh_funcs = {}

        # Helper to create tab content
        def create_list_tab(mgr, tag):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            search = QLineEdit()
            search.setPlaceholderText("搜索元素...")
            layout.addWidget(search)
            lst = QListWidget()
            layout.addWidget(lst)
            
            def populate(filter_text=""):
                data = mgr.list_elements() if mgr else {}
                
                # Flatten
                items = []
                if isinstance(data, dict):
                    for group, group_items in data.items():
                        if not isinstance(group_items, dict):
                            continue
                        for name, meta in group_items.items():
                            by = meta.get("by") if isinstance(meta, dict) else ""
                            value = meta.get("value") if isinstance(meta, dict) else ""
                            key = f"{group}/{name}"
                            items.append((key, by, value))
                items.sort(key=lambda x: x[0])

                lst.clear()
                ft = (filter_text or "").lower()
                for key, by, value in items:
                    if ft in key.lower():
                        item = QListWidgetItem(f"{key}  [{by}]")
                        item.setData(Qt.UserRole, {"key": key, "by": by, "value": value})
                        lst.addItem(item)
            
            populate()
            search.textChanged.connect(populate)
            refresh_funcs[tag] = lambda: populate(search.text())
            return tab, lst
        
        # Create Tabs
        p_tab, p_list = create_list_tab(private_mgr, "private")
        tab_widget.addTab(p_tab, "当前流程元素")
        
        g_tab, g_list = create_list_tab(global_mgr, "global")
        tab_widget.addTab(g_tab, "全局/历史元素")
        
        main_layout.addWidget(tab_widget)
        
        # Create New Element Logic
        def open_create_dialog():
            if not private_mgr:
                QMessageBox.warning(dlg, "错误", "无法访问私有元素库，请确保工作流已加载。")
                return

            cdlg = QDialog(dlg)
            cdlg.setWindowTitle("新建元素")
            cdlg.resize(400, 300)
            clayout = QFormLayout(cdlg)
            
            # Inputs
            group_input = QComboBox()
            group_input.setEditable(True)
            # Pre-fill groups
            existing = private_mgr.list_elements() or {}
            for g in existing.keys():
                group_input.addItem(g)
            if group_input.count() == 0:
                group_input.addItem("Default")
            
            name_input = QLineEdit()
            by_input = QComboBox()
            by_input.addItems(["xpath", "css", "id", "name", "class_name", "tag_name", "link_text", "partial_link_text"])
            value_input = QLineEdit()
            desc_input = QLineEdit()
            
            clayout.addRow("分组:", group_input)
            clayout.addRow("名称:", name_input)
            clayout.addRow("定位方式:", by_input)
            clayout.addRow("定位值:", value_input)
            clayout.addRow("备注:", desc_input)
            
            # Buttons
            cbtn_box = QHBoxLayout()
            cbtn_ok = QPushButton("保存")
            cbtn_cancel = QPushButton("取消")
            cbtn_box.addWidget(cbtn_cancel)
            cbtn_box.addWidget(cbtn_ok)
            clayout.addRow(cbtn_box)
            
            def save_new():
                group = group_input.currentText().strip() or "Default"
                name = name_input.text().strip()
                by = by_input.currentText()
                value = value_input.text().strip()
                
                if not name or not value:
                    QMessageBox.warning(cdlg, "错误", "名称和定位值不能为空！")
                    return
                
                meta = {"description": desc_input.text().strip()}
                try:
                    private_mgr.save_element(group, name, by, value, meta)
                    cdlg.accept()
                except Exception as e:
                    QMessageBox.warning(cdlg, "保存失败", str(e))

            cbtn_ok.clicked.connect(save_new)
            cbtn_cancel.clicked.connect(cdlg.reject)
            
            if cdlg.exec():
                # Refresh private list
                if "private" in refresh_funcs:
                    refresh_funcs["private"]()
                # Switch to private tab
                tab_widget.setCurrentIndex(0)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        btn_new = QPushButton("新建元素")
        btn_ok = QPushButton("确认")
        btn_cancel = QPushButton("取消")
        
        btn_box.addWidget(btn_new)
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        main_layout.addLayout(btn_box)
        
        btn_new.clicked.connect(open_create_dialog)

        def apply_selected():
            current_tab_idx = tab_widget.currentIndex()
            current_list = p_list if current_tab_idx == 0 else g_list
            item = current_list.currentItem()
            
            if not item:
                return
            
            data = item.data(Qt.UserRole)
            key = data["key"]
            
            # If selected from Global, copy to Private
            if current_tab_idx == 1 and private_mgr:
                # Check if file path is set for private mgr
                if not private_mgr.file_path:
                    pass
                
                parts = key.split("/", 1)
                group = parts[0] if len(parts) > 0 else "Default"
                name = parts[1] if len(parts) > 1 else key
                
                private_mgr.save_element(group, name, data["by"], data["value"])
                
                # Refresh private list to show the new item
                if "private" in refresh_funcs:
                    refresh_funcs["private"]()
            
            # Set text to widget
            if isinstance(target_widget, QLineEdit): target_widget.setText(key)
            elif isinstance(target_widget, QTextEdit): target_widget.setPlainText(key)
            elif isinstance(target_widget, QComboBox): target_widget.setEditText(key)
            
            dlg.accept()

        btn_ok.clicked.connect(apply_selected)
        btn_cancel.clicked.connect(dlg.reject)
        p_list.itemDoubleClicked.connect(lambda _: apply_selected())
        g_list.itemDoubleClicked.connect(lambda _: apply_selected())
        
        dlg.exec()
