# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

class ImageDropWidget(QFrame):
    image_dropped = Signal(str) # Path to image
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = ""
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #333;
                border-radius: 10px;
                background: #0A0A0A;
            }
            QFrame:hover {
                border-color: #FFBF00;
                background: #111;
            }
        """)
        
        layout = QVBoxLayout(self)
        self.label = QLabel("将图片拖拽至此或点击上传\n(支持 PNG, JPG, JPEG)")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(self.label)
        
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.hide()
        layout.addWidget(self.preview)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet(self.styleSheet().replace("#333", "#FFBF00"))
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("#FFBF00", "#333"))

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            path = files[0]
            if path.lower().endswith(('.png', '.jpg', '.jpeg')):
                self.show_preview(path)
                self.image_dropped.emit(path)
        self.setStyleSheet(self.styleSheet().replace("#FFBF00", "#333"))

    def mousePressEvent(self, event):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择参考图像", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.show_preview(path)
            self.image_dropped.emit(path)

    def show_preview(self, path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.label.hide()
            self.file_path = path
            scaled = pixmap.scaled(300, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview.setPixmap(scaled)
            self.preview.show()
            self.setStyleSheet(self.styleSheet().replace("#333", "#00E676")) # Green for ready

    def clear(self):
        self.file_path = ""
        self.preview.hide()
        self.label.show()
        self.setStyleSheet(self.styleSheet().replace("#00E676", "#333"))
