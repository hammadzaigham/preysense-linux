"""Read-only, local Linux documentation viewer in the existing PreySense shell."""
from pathlib import Path
from PySide6.QtCore import QUrl,Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QTextBrowser,QWidget,QFrame
try:
    from window_chrome import WindowTitleBar
except ImportError:
    from linux.window_chrome import WindowTitleBar

class DocumentationWindow(QDialog):
    def __init__(self,parent):
        super().__init__(parent);self.setWindowTitle('PreySense • Linux Documentation');self.resize(760,660)
        self.root=Path(__file__).resolve().parents[1];self.history=[]
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
        root.addWidget(WindowTitleBar(self,'Linux Documentation'))
        content=QWidget();layout=QVBoxLayout(content);layout.setContentsMargins(14,10,14,8);layout.setSpacing(8);root.addWidget(content)
        row=QHBoxLayout();row.setSpacing(8)
        back=QPushButton('Back');back.setFixedHeight(28);back.clicked.connect(self.back);row.addWidget(back)
        home=QPushButton('Linux Documentation');home.setFixedHeight(28);home.clicked.connect(lambda:self.load(self.root/'docs/linux/README.md'));row.addWidget(home);row.addStretch()
        layout.addLayout(row)
        self.browser=QTextBrowser();self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.browser.setFrameShape(QFrame.NoFrame);self.browser.setOpenLinks(False);self.browser.anchorClicked.connect(self.follow);layout.addWidget(self.browser)
        self.load(self.root/'docs/linux/README.md')
    def load(self,path,record=True):
        path=Path(path).resolve()
        if not path.is_relative_to(self.root) or path.suffix!='.md':return
        if record:self.history.append(path)
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(path.parent)+'/'))
        try:self.browser.setMarkdown(path.read_text())
        except OSError:self.browser.setPlainText('Linux documentation is not installed. Run the current linux/install.sh from the development checkout.')
    def back(self):
        if len(self.history)>1:self.history.pop();self.load(self.history[-1],False)
    def follow(self,url):
        if url.scheme() in ('http','https'):QDesktopServices.openUrl(url);return
        resolved=self.browser.document().baseUrl().resolved(url)
        if resolved.isLocalFile():
            self.load(resolved.toLocalFile())
            if resolved.fragment():self.browser.scrollToAnchor(resolved.fragment())
