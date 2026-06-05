from PyQt6.QtWidgets import QFrame


class VerticalLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(self.Shape.VLine)
        self.setFrameShadow(self.Shadow.Sunken)
