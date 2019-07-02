import sys
import time

import requests

from PySide2.QtCore import QRect, QSize, QPoint, Signal, Slot, Qt, QByteArray, QBuffer
from PySide2.QtWidgets import QWidget, QApplication, QRubberBand
from PySide2.QtGui import QMouseEvent, QPixmap, QPixelFormat
from mainwin_ui import Ui_MainForm
from settingswin_ui import Ui_SettingsForm

from aip import AipOcr

class Scrot(QWidget):

    scrotFinished = Signal(QPixmap)

    def __init__(self, parent: QWidget = None):
        super(Scrot, self).__init__(parent=parent)
        self.rubberBand: QRubberBand = None
        self.origin: QPoint = QPoint()
        self.screen = QApplication.primaryScreen()
        self.setWindowOpacity(0.1)

    def mousePressEvent(self, event: QMouseEvent):
        self.origin = event.pos()
        if self.rubberBand is None:
            self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.rubberBand.setGeometry(QRect(self.origin, QSize()))
        self.rubberBand.show()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.rubberBand is not None:
            self.rubberBand.setGeometry(QRect(self.origin, event.pos()).normalized())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.rubberBand is not None:
            self.rubberBand.hide()
            self.close()
            time.sleep(0.6)
            rect = (min(self.origin.x(), event.x()), min(self.origin.y(), event.y()), abs(event.x() - self.origin.x()),
                                                     abs(event.y() - self.origin.y()))
            screenShot = self.screen.grabWindow(QApplication.desktop().winId(), *rect)
            self.scrotFinished.emit(screenShot)

    def run(self):
        self.showFullScreen()

class SettingsWin(QWidget):
    apiConfigured = Signal(tuple)

    def __init__(self, api_id: str, api_key: str, secret_key: str, parent=None):
        super(SettingsWin, self).__init__(parent=parent)
        self.ui = Ui_SettingsForm()
        self.ui.setupUi(self)

        self.setFixedHeight(self.height())

        self.ui.lineEdit.setText(api_id)
        self.ui.lineEdit_2.setText(api_key)
        self.ui.lineEdit_3.setText(secret_key)

        self.ui.assertButton.setDisabled(True)
        self.ui.pushButton.clicked.connect(self.ok)
        self.ui.pushButton_2.clicked.connect(self.cancel)

    def ok(self):
        self.apiConfigured.emit((self.ui.lineEdit.text(), self.ui.lineEdit_2.text(), self.ui.lineEdit_3.text()))
        self.close()

    def cancel(self):
        self.close()

class MainWin(QWidget):

    searchSignal = Signal(str, str)

    def __init__(self):
        super(MainWin, self).__init__()
        self.ui = Ui_MainForm()
        self.ui.setupUi(self)

        self.setFixedSize(self.width(), self.height())

        self.scrot = None
        self.settings = None

        self.session = requests.Session()
        self.session.headers = {
            'Content-type': 'application/x-www-form-urlencoded'
        }

        self.app_id = '16512590'
        self.app_key = '9cBepWNaqqXxLnUL25IMG72D'
        self.secret_key = 'EpDomzk5i95omRQW9f6qedGFWeXXQYb3'

        self.client = AipOcr(self.app_id, self.app_key, self.secret_key)

        # bind
        self.ui.scrotButton.clicked.connect(self.onScrotButtonClicked)
        self.ui.settingButton.clicked.connect(self.onSettingsButtonClicked)
        self.ui.searchButton.clicked.connect(self.onSearchButtonClicked)
        self.searchSignal.connect(self.search)

    @Slot(QPixmap)
    def prnt(self, screenShot: QPixmap):
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        screenShot.save(buffer, 'png')
        data = buffer.data().data()
        res = self.client.basicGeneral(data)
        if 'words_result_num' in res.keys():
            print('[ INFO ] 识别成功')
            text = ''
            result = res['words_result']
            d = {
                '单选题': self.ui.rad_1,
                '多选题': self.ui.rad_2,
                '填空题': self.ui.rad_3,
                '问答题': self.ui.rad_4,
                '判断题': self.ui.rad_14,
                '分析题': self.ui.rad_5,
                '解答题': self.ui.rad_5,
                '计算题': self.ui.rad_5,
                '证明题': self.ui.rad_5,
            }
            for words in result:
                ques_type = False
                for k in d.keys():
                    if k in words['words']:
                        ques_type = True
                        print('[ INFO ] 题目类型:', k)
                        d[k].setChecked(True)
                        d[k].repaint()
                        break
                if not ques_type:
                    text += words['words']
            text = text.replace('(', '（').replace(')', '）').replace('?', '？').replace(',', '，')
            print('[ INFO ] 题目:', text)
            self.ui.questLineEdit.setText(text)
            self.ui.questLineEdit.repaint()
            self.ui.searchButton.click()
        else:
            print('[ INFO ] 识别失败')

    @Slot(tuple)
    def setApiKey(self, newPair: tuple):
        self.app_id, self.app_key, self.secret_key = newPair

    def onSettingsButtonClicked(self):
        self.settings = SettingsWin(self.app_id, self.app_key, self.secret_key)
        self.settings.apiConfigured.connect(self.setApiKey)
        self.settings.show()

    def onScrotButtonClicked(self):
        self.scrot = Scrot()
        self.scrot.scrotFinished.connect(self.prnt)
        self.scrot.run()

    def onSearchButtonClicked(self):
        self.ui.searchButton.setDisabled(True)
        self.ui.searchButton.repaint()
        type_btn = self.ui.typeBtnGroup.checkedButton()
        text = self.ui.questLineEdit.text()
        if len(text) <= 1:
            self.ui.searchButton.setDisabled(False)
            self.ui.searchButton.repaint()
            return
        typ = '' if type_btn is None else type_btn.objectName()[4:]
        self.searchSignal.emit(typ, text)

    @Slot(str, str)
    def search(self, typ: str, text: str):
        print('[ INFO ] 正在查找')
        self.ui.textBrowser.setText('正在查找...')
        self.ui.textBrowser.repaint()
        if typ == '':
            res = self.session.post('http://mooc.forestpolice.org/zhs/0/' + text).json()
        else:
            res = self.session.post('http://mooc.forestpolice.org/zhs/0/' + text, data={'type': typ}).json()
        print(res['code'])
        if res['code'] == -1:
            print('[FAILED] 查找失败')
            self.ui.textBrowser.setText('未找到答案\n可以尝试从后往前删除一些内容来重新搜索\n以便提高搜索成功率')
            self.ui.searchButton.setDisabled(False)
        else:
            print('[  OK  ] 查找成功')
            print('[ INFO ]', res['data'])
            self.ui.textBrowser.setText(res['data'].replace('#', '\n'))
            self.ui.searchButton.setDisabled(False)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    mainwin = MainWin()
    mainwin.show()

    sys.exit(app.exec_())
