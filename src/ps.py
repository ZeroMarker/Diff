from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
import sys

app = QApplication(sys.argv)
window = QMainWindow()
window.setWindowTitle("PySide6 示例")

central_widget = QWidget()
layout = QVBoxLayout()
button = QPushButton("点击我！")
layout.addWidget(button)
central_widget.setLayout(layout)
window.setCentralWidget(central_widget)

window.show()
sys.exit(app.exec())