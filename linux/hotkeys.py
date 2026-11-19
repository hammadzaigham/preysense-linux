"""Predator key count and bounded vendor-HID hotkeys; no global keyboard grab."""
import os,time,select
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QTimer,QSocketNotifier,Qt

BRIGHTNESS_DOWN = frozenset((0x11, 0x1A, 0x44, 0x57, 0x78, 0x7A, 0x7D, 0x8B, 0xC5))
BRIGHTNESS_UP = frozenset((0x12, 0x1B, 0x45, 0x58, 0x07, 0x79, 0x7C, 0x8C, 0xC4))

def classify_report(report):
    if len(report)<2 or report[0]!=4:return None
    if len(report) >= 3 and report[2] == 0xFF:
        if report[1] in BRIGHTNESS_DOWN:
            return 'brightness_down'
        if report[1] in BRIGHTNESS_UP:
            return 'brightness_up'
    if report[1]==0x85 or (len(report)>=3 and report[1]==5 and report[2]==1):return 'turbo'
    if len(report)>=3 and report[1]==0x75 and report[2]==0xff:return 'predator'
    return None

def next_mode(current,ac):
    # One predictable cycle on every power source. Keep ac for call compatibility.
    return {6:0,0:1,1:4,4:5,5:6}.get(current,6)

PREDATOR_BOUNCE_SECONDS = .08

class Hotkeys(QObject):
    predator=Signal()
    turbo=Signal()
    mode=Signal(int)
    overlay=Signal()
    keyboard_brightness=Signal(int)
    def __init__(self,parent=None,root=Path('/sys')):
        super().__init__(parent);self.root=Path(root);self.fd=None;self.notifier=None;self.count=None;self.last={'predator':float('-inf'),'turbo':float('-inf')};self.shortcuts=None
        self.event_fds={};self.event_poll=None;self.event_notifier=None
        self.brightness_steps=None
        self.last_brightness = None
        self.fallback_baseline=None
        self.fallback_timer=QTimer(self);self.fallback_timer.setSingleShot(True);self.fallback_timer.timeout.connect(lambda:self.predator_fallback(self.fallback_baseline))
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.setTimerType(Qt.PreciseTimer)
        self.poll()
        if not self.start_events():self.timer.start(25)
    def start_events(self):
        native=self.root/'devices/platform/preysense'
        try:
            if (native/'event_notifications').read_text().strip()!='1':return False
            self.event_poll=select.epoll()
            for name in ('predator_events','shortcut_events','keyboard_brightness_steps'):
                try:
                    fd=os.open(native/name,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC)
                except FileNotFoundError:
                    if name == 'keyboard_brightness_steps':
                        continue
                    raise
                self.event_fds[name]=fd
                os.read(fd,4096)  # Acknowledge the current sysfs generation.
                self.event_poll.register(fd,select.EPOLLPRI|select.EPOLLERR)
            self.event_notifier=QSocketNotifier(self.event_poll.fileno(),QSocketNotifier.Read,self)
            self.event_notifier.activated.connect(self.event_ready)
            # Close the startup race between baseline sampling and registration.
            self.poll()
            return True
        except (OSError,ValueError):
            self.close_events();return False
    def close_events(self):
        if self.event_notifier:
            self.event_notifier.setEnabled(False);self.event_notifier.deleteLater();self.event_notifier=None
        if self.event_poll:self.event_poll.close();self.event_poll=None
        for fd in self.event_fds.values():os.close(fd)
        self.event_fds={}
    def event_ready(self,*_):
        try:
            if self.event_poll.poll(0):self.poll()
        except OSError:self.close_events();self.timer.start(25)
    def counter(self,name):
        fd=self.event_fds.get(name)
        if fd is None:return (self.root/'devices/platform/preysense'/name).read_text()
        os.lseek(fd,0,os.SEEK_SET)
        return os.read(fd,4096).decode('ascii')
    def dispatch(self,kind):
        now=time.monotonic()
        debounce=PREDATOR_BOUNCE_SECONDS if kind=='predator' else .35
        if now-self.last[kind]<debounce:return
        self.last[kind]=now
        if kind=='turbo':self.turbo.emit();return
        self.predator.emit()
    def dispatch_brightness(self, steps, source):
        if not steps:
            return
        now = time.monotonic()
        if self.last_brightness is not None and abs(steps) == 1:
            last_time, last_steps, last_source = self.last_brightness
            interval = .03 if source == last_source == 'hid' else .10
            if steps == last_steps and now - last_time < interval and (
                source != last_source or source == 'hid'
            ):
                return
        self.last_brightness = (now, steps, source)
        self.keyboard_brightness.emit(steps)
    def poll(self):
        try:
            count=int(self.counter('predator_events'))
            if self.count is not None and count>self.count:
                if (count-self.count)%2:self.dispatch('predator')
            self.count=count
        except (OSError,ValueError):self.count=None
        try:
            serial,number,overlay=map(int,self.counter('shortcut_events').split())
            if self.shortcuts is not None:
                if serial>self.shortcuts[0] and 1<=number<=5:self.mode.emit((6,0,1,4,5)[number-1])
                if overlay>self.shortcuts[1] and (overlay-self.shortcuts[1])%2:self.overlay.emit()
            self.shortcuts=(serial,overlay)
        except (OSError,ValueError):self.shortcuts=None
        try:
            steps = int(self.counter('keyboard_brightness_steps'))
            if self.brightness_steps is not None and steps != self.brightness_steps:
                delta = (steps - self.brightness_steps + 2**31) % 2**32 - 2**31
                self.dispatch_brightness(delta, 'evdev')
            self.brightness_steps = steps
        except (OSError, ValueError):
            self.brightness_steps = None
        if self.fd is None:
            for p in (self.root/'class/hidraw').glob('hidraw*'):
                try:
                    if 'HID_ID=0018:00001025:0000174B' not in (p/'device/uevent').read_text():continue
                    self.fd=os.open('/dev/'+p.name,os.O_RDONLY|os.O_NONBLOCK)
                    self.notifier=QSocketNotifier(self.fd,QSocketNotifier.Read,self)
                    self.notifier.activated.connect(self.read_ready)
                    break
                except OSError:continue
    def predator_report(self):
        if self.count is None:self.dispatch('predator');return
        if not self.fallback_timer.isActive():
            self.fallback_baseline=self.count;self.fallback_timer.start(100)
    def predator_fallback(self,baseline):
        try:
            native=self.root/'devices/platform/preysense'
            count=int((native/'predator_events').read_text())
            held=(native/'predator_down').read_text().strip()=='1'
            # Native press/release or modifier ownership wins; HID-only models
            # can still toggle when neither native path observed this report.
            if count==baseline and not held:self.dispatch('predator')
        except (OSError,ValueError):pass
    def read_ready(self,*_):
        try:
            while True:
                data=os.read(self.fd,4096)
                if not data:self.close();return
                kind=classify_report(data)
                if kind=='predator':self.predator_report()
                elif kind=='brightness_down':self.dispatch_brightness(-1, 'hid')
                elif kind=='brightness_up':self.dispatch_brightness(1, 'hid')
                elif kind:self.dispatch(kind)
        except BlockingIOError:pass
        except OSError:self.close()
    def close(self):
        self.fallback_timer.stop()
        if self.notifier:self.notifier.setEnabled(False);self.notifier.deleteLater();self.notifier=None
        if self.fd is not None:os.close(self.fd);self.fd=None
    def stop(self):self.timer.stop();self.close();self.close_events()
