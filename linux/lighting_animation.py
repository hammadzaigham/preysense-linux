"""Worker-thread animation scheduler, with native key-idle timeout and EC recovery."""
import time
from PySide6.QtCore import QObject,QTimer
from lighting_effects import SOFTWARE_EFFECTS,frame
from hardware import average_color

class LightingAnimation(QObject):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.active=False;self.restore_timeout=0;self.last=None;self.timeout=0
    @property
    def hardware(self):return self.owner.hardware
    def start(self,args):
        self.stop()
        self.args=dict(args)
        if args['effect'] not in SOFTWARE_EFFECTS:raise ValueError('Unknown software effect')
        if not 0<=args['brightness']<=100 or not 0<=args['speed']<=10:raise ValueError('Invalid animation settings')
        self.restore_timeout=int(self.hardware.bridge_read('led_timeout') or 0);self.timeout=self.restore_timeout
        self.hardware.write('led_timeout',0)
        self.started=time.monotonic();self.wake_at=self.started;self.last=None;self.active=True
        self.timer.start(max(70,180-args['speed']*11));self.tick()
    def tick(self):
        if not self.active:return
        try:
            elapsed=time.monotonic()-self.started
            idle=self.hardware.bridge_read('keyboard_idle_ms')
            dim=self.timeout>0 and idle is not None and min(float(idle)/1000,time.monotonic()-self.wake_at)>=self.timeout
            # Idle effects need no animation frames; keep wake latency <=200ms.
            interval=200 if dim else max(70,180-self.args['speed']*11)
            if self.timer.interval()!=interval:self.timer.setInterval(interval)
            speed=self.args['speed']*10
            colors=[(0,0,0)]*4 if dim else frame(self.args['effect'],elapsed/.028*(.03+speed/100*.32),int(elapsed/.028),tuple(self.args['colors'][0]),speed)
            brightness=0 if dim else self.args['brightness']
            signature=(tuple(colors),brightness)
            if signature!=self.last:
                self.hardware.lighting(colors,brightness,'Static',self.args['speed'])
                if self.args.get('sync_logo'):self.hardware.logo_lighting(average_color(colors),brightness,'Static',self.args['speed'])
                self.last=signature
                self.owner.lighting_frame.emit(colors)
        except Exception as exc:
            try:self.stop()
            except Exception as recovery:exc=RuntimeError(f'{exc}; recovery: {recovery}')
            self.owner.done.emit('Lighting animation',str(exc))
    def stop(self):
        self.timer.stop()
        if self.active:
            self.active=False
            try:
                self.hardware.lighting(self.args['colors'],self.args['brightness'],'Static',self.args['speed'])
                if self.args.get('sync_logo'):self.hardware.logo_lighting(average_color(self.args['colors']),self.args['brightness'],'Static',self.args['speed'])
            finally:self.hardware.write('led_timeout',self.restore_timeout)
        self.last=None
