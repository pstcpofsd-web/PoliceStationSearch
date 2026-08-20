import sys, re, time, html
import requests
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QListWidget, QListWidgetItem, QDialog, QComboBox, QTextEdit

GOOGLE_SHEET_API = "https://script.google.com/macros/s/AKfycbzsZY4QHGaskZwoXyrnmGSObPzDdo8U-DhfSKSSfzPmsKUCGoFNkQL4EsBsf20_H_PY/exec"

def expand_areas(data):
    out=[]
    for x in data:
        ps=str(x.get("ps","") or "").strip()
        raw=str(x.get("area","") or "")
        parts=[p.strip() for p in re.split(r"[,،/\n]+",raw) if p.strip()]
        for p in (parts or [""]):
            out.append({"ps":ps,"area":p})
    return out

def approved_records(data):
    out=[]
    for x in data:
        s=str(x.get("status",x.get("Status",x.get("approval",""))) or "").strip().lower()
        if not s or s in {"approved","approve","yes","true","1"}:
            out.append(x)
    return out

class Worker(QThread):
    ok=Signal(list); fail=Signal(str)
    def run(self):
        try:
            r=requests.get(GOOGLE_SHEET_API,params={"t":time.time()},timeout=20)
            r.raise_for_status()
            d=r.json()
            if not isinstance(d,list): raise ValueError("Invalid data received")
            self.ok.emit(approved_records(d))
        except Exception as e:
            self.fail.emit(str(e))

class DialogBase(QDialog):
    submitted=Signal()
    def post(self,payload,msg):
        try:
            r=requests.post(GOOGLE_SHEET_API,json=payload,timeout=20)
            d=r.json()
            if d.get("status")!="success":
                raise RuntimeError(d.get("message","Save failed"))
            msg.setText("✅ Successfully saved as Pending")
            self.submitted.emit()
        except Exception as e:
            msg.setText("❌ "+str(e))

class AddDialog(DialogBase):
    def __init__(self,stations,parent=None):
        super().__init__(parent); self.setWindowTitle("➕ Add Area"); self.resize(430,230)
        l=QVBoxLayout(self); l.addWidget(QLabel("➕ Naya Area Add Karein"))
        l.addWidget(QLabel("Police Station منتخب کریں")); self.ps=QComboBox(); self.ps.addItems(stations); l.addWidget(self.ps)
        l.addWidget(QLabel("Area of Police Station لکھیں")); self.area=QLineEdit(); self.area.setPlaceholderText("مثال: Model Town Block A"); l.addWidget(self.area)
        self.msg=QLabel(""); l.addWidget(self.msg)
        b=QHBoxLayout(); c=QPushButton("Cancel"); c.clicked.connect(self.reject); s=QPushButton("💾 Save"); s.clicked.connect(self.submit); b.addWidget(c); b.addWidget(s); l.addLayout(b)
    def submit(self):
        ps=self.ps.currentText().strip(); area=self.area.text().strip()
        if not ps: self.msg.setText("⚠️ Police Station منتخب کریں"); return
        if not area: self.msg.setText("⚠️ Area لکھیں"); return
        self.msg.setText("⏳ Save ہو رہا ہے..."); QApplication.processEvents()
        self.post({"action":"add","ps":ps,"area":area,"status":"Pending"},self.msg)

class CorrectionDialog(DialogBase):
    def __init__(self,stations,parent=None):
        super().__init__(parent); self.setWindowTitle("✏️ Correction"); self.resize(450,290)
        l=QVBoxLayout(self); l.addWidget(QLabel("✏️ Correction Submit Karein"))
        l.addWidget(QLabel("Police Station منتخب کریں")); self.ps=QComboBox(); self.ps.addItems(stations); l.addWidget(self.ps)
        l.addWidget(QLabel("Correction لکھیں")); self.correction=QTextEdit(); self.correction.setPlaceholderText("Correction لکھیں..."); l.addWidget(self.correction)
        self.msg=QLabel(""); l.addWidget(self.msg)
        b=QHBoxLayout(); c=QPushButton("Cancel"); c.clicked.connect(self.reject); s=QPushButton("💾 Submit"); s.clicked.connect(self.submit); b.addWidget(c); b.addWidget(s); l.addLayout(b)
    def submit(self):
        ps=self.ps.currentText().strip(); correction=self.correction.toPlainText().strip()
        if not ps: self.msg.setText("⚠️ Police Station منتخب کریں"); return
        if not correction: self.msg.setText("⚠️ Correction لکھیں"); return
        self.msg.setText("⏳ Correction Save ہو رہی ہے..."); QApplication.processEvents()
        self.post({"action":"correction","ps":ps,"correction":correction,"status":"Pending"},self.msg)

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Police Station Area Search"); self.resize(1050,650); self.raw=[]; self.records=[]
        w=QWidget(); self.setCentralWidget(w); l=QVBoxLayout(w); l.setContentsMargins(25,25,25,25)
        h=QLabel("🛡️ Find Your Police Station"); h.setObjectName("heading"); h.setAlignment(Qt.AlignCenter); l.addWidget(h)
        s=QLabel("📍 Search Area   •   🚓 Police Station"); s.setAlignment(Qt.AlignCenter); l.addWidget(s)
        bar=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search area / police station..."); self.search.textChanged.connect(self.search_data); bar.addWidget(self.search)
        b=QPushButton("✕ Clear"); b.clicked.connect(self.search.clear); bar.addWidget(b)
        b=QPushButton("➕ Add"); b.clicked.connect(self.add); bar.addWidget(b)
        b=QPushButton("✏️ Correction"); b.clicked.connect(self.correction); bar.addWidget(b)
        l.addLayout(bar)
        self.list=QListWidget(); self.list.itemClicked.connect(self.select); l.addWidget(self.list,1)
        self.info=QLabel("🚓 Total Police Stations: 0    👁️ Showing: 0"); l.addWidget(self.info)
        f=QLabel("Police Station Search System\nDeveloped by Majid Ali HC"); f.setAlignment(Qt.AlignCenter); l.addWidget(f)
        self.setStyleSheet("QWidget{background:#f3eee5;color:#2f241d;font-family:'Segoe UI';font-size:14px} #heading{font-size:30px;font-weight:700;color:#3f281d} QLineEdit,QComboBox,QTextEdit{background:white;border:1px solid #d9c7b8;border-radius:14px;padding:10px} QPushButton{background:#c87941;color:white;border:0;border-radius:12px;padding:10px 17px} QListWidget{background:white;border:1px solid #eaded3;border-radius:15px} QListWidget::item{padding:10px} QListWidget::item:selected{background:#f1e2d5;color:#2f241d}")
        self.toast=QLabel(self); self.toast.setStyleSheet("background:#8a5a34;color:white;border-radius:12px;padding:10px 20px"); self.toast.hide()
        self.load()

    def resizeEvent(self,e):
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast.adjustSize(); self.toast.move((self.width()-self.toast.width())//2,15)

    def toast_msg(self,a,b="Mr. Majid Ali"):
        self.toast.setText(f"<b>{html.escape(a)}</b><br><small>{html.escape(b)}</small>")
        self.toast.adjustSize(); self.toast.move((self.width()-self.toast.width())//2,15); self.toast.show()
        QTimer.singleShot(3500,self.toast.hide)

    def load(self):
        self.toast_msg("⏳ Wait data is loading...","Developed by Mr. Majid Ali")
        self.worker=Worker(); self.worker.ok.connect(self.loaded); self.worker.fail.connect(lambda e:self.toast_msg("❌ Failed to Load Data",e)); self.worker.start()

    def loaded(self,d):
        self.raw=d; self.records=expand_areas(d); self.toast_msg("✅ You Can Search Now...","Mr. Majid Ali"); self.update_info(0)

    def update_info(self,n):
        self.info.setText(f"🚓 Total Police Stations: {len({x.get('ps') for x in self.raw if x.get('ps')})}    👁️ Showing: {n}")

    def search_data(self,t):
        self.list.clear(); q=t.strip().lower()
        if not q: self.update_info(0); return
        m=[x for x in self.records if q in x["area"].lower() or q in x["ps"].lower()]
        for x in m[:100]:
            i=QListWidgetItem(f"✨ {x['area']}\n🚓 {x['ps']}"); i.setData(Qt.UserRole,x); self.list.addItem(i)
        self.update_info(len(m))

    def select(self,i):
        x=i.data(Qt.UserRole); self.search.setText(f"{x['area']} - {x['ps']}")

    def stations(self):
        return sorted({str(x.get("ps","")).strip() for x in self.raw if str(x.get("ps","")).strip()})

    def add(self):
        d=AddDialog(self.stations(),self); d.submitted.connect(self.load); d.exec()

    def correction(self):
        d=CorrectionDialog(self.stations(),self); d.submitted.connect(self.load); d.exec()

if __name__=="__main__":
    app=QApplication(sys.argv); app.setFont(QFont("Segoe UI",10)); win=Main(); win.show(); sys.exit(app.exec())
