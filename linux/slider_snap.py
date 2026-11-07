"""Windows-style slider tick snapping for pointer, keyboard and wheel input."""
from PySide6.QtCore import QObject,QEvent,Qt
from PySide6.QtWidgets import QStyle,QStyleOptionSlider
class SliderSnap(QObject):
    def __init__(self,slider,step,page=None):
        super().__init__(slider);self.slider=slider;self.step=step
        slider.setSingleStep(step);slider.setPageStep(page if page is not None else step)
        slider.setTickInterval(step);slider.installEventFilter(self)
    def snap(self,value):
        s=self.slider;minimum=s.minimum()
        value=minimum+((int(value)-minimum+self.step//2)//self.step)*self.step
        return max(minimum,min(s.maximum(),value))
    def eventFilter(self,obj,event):
        s=self.slider;t=event.type()
        if not s.isEnabled():return False
        if t in (QEvent.MouseButtonPress,QEvent.MouseMove,QEvent.MouseButtonRelease):
            if t!=QEvent.MouseMove and event.button()!=Qt.LeftButton:return False
            if t==QEvent.MouseMove and not s.isSliderDown():return False
            option=QStyleOptionSlider();s.initStyleOption(option)
            handle=s.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,s)
            vertical=s.orientation()==Qt.Vertical;extent=handle.height() if vertical else handle.width()
            span=(s.height() if vertical else s.width())-extent
            pos=(event.position().y() if vertical else event.position().x())-extent/2
            value=QStyle.sliderValueFromPosition(s.minimum(),s.maximum(),round(pos),max(1,span),option.upsideDown)
            if t==QEvent.MouseButtonPress:s.setSliderDown(True)
            s.setValue(self.snap(value))
            if t==QEvent.MouseButtonRelease:s.setSliderDown(False)
            event.accept();return True
        if t==QEvent.Wheel:
            delta=event.angleDelta().y();s.setValue(self.snap(s.value()+(self.step if delta>0 else -self.step)))
            event.accept();return True
        return False

def configure_snap(slider,step,page=None):
    old=getattr(slider,'_preysense_snap',None)
    if old:slider.removeEventFilter(old);old.deleteLater()
    slider._preysense_snap=SliderSnap(slider,step,page)
