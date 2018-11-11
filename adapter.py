import win32ui
import win32gui
import win32con
import numpy as np
from PIL import Image
from time import sleep
from threading import Thread, Lock
from tesserocr import PyTessBaseAPI, PSM, OEM
from contextlib import contextmanager


class GameAdaptor:

    def __init__(self, window_name):
        self._window_name = window_name
        self._hwnd = win32gui.FindWindow(None, window_name)
        _options = dict(psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY)
        self._api = PyTessBaseAPI('tessdata', 'eng', **_options)
        self._image = None
        self._lock = Lock()
        self._work = 0
        if self._hwnd == 0:
            raise Exception('Window Handle Not Found! xD')

    def _get_window_region(self):
        bl, bt, br, bb = 12, 31, 12, 20
        l, t, r, b = win32gui.GetWindowRect(self._hwnd)
        w = r - l - br - bl
        h = b - t - bt - bb
        return l, t, w, h, bl, bt

    @contextmanager
    def _window_device_context(self):
        wdc = win32gui.GetWindowDC(self._hwnd)
        dc_obj = win32ui.CreateDCFromHandle(wdc)
        c_dc = dc_obj.CreateCompatibleDC()
        yield dc_obj, c_dc
        dc_obj.DeleteDC()
        c_dc.DeleteDC()
        win32gui.ReleaseDC(self._hwnd, wdc)

    def _capture(self):
        x, y, w, h, bx, by = self._get_window_region()
        with self._window_device_context() as (dc_obj, cdc):
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(dc_obj, w, h)
            cdc.SelectObject(bmp)
            cdc.BitBlt((0, 0), (w, h), dc_obj, (bx, by), win32con.SRCCOPY)
            bmp_info = bmp.GetInfo()
            img = np.frombuffer(bmp.GetBitmapBits(True), dtype=np.uint8)
            win32gui.DeleteObject(bmp.GetHandle())
        return img.reshape(bmp_info['bmHeight'], bmp_info['bmWidth'], 4)[:, :, :-1]

    def _do_capture(self):
        while self._work == 1:
            temp_image = self._capture()
            self._lock.acquire()
            self._image = temp_image
            self._lock.release()
            sleep(0.001)
        self._work = -1

    def start_capture(self):
        self._work = 1
        Thread(target=self._do_capture).start()
        while self._image is None:
            sleep(0.001)

    def stop_capture(self):
        self._work = 0
        while self._work != -1:
            sleep(0.001)
        self._image = None

    def get_image(self):
        self._lock.acquire()
        res = self._image
        self._lock.release()
        return res

    def send_keys(self, *keys):
        for k in keys:
            win32gui.PostMessage(self._hwnd, win32con.WM_KEYDOWN, k, 0)

    def get_text(self, region):
        temp_pil_image = Image.fromarray(self.get_image())
        self._api.SetImage(temp_pil_image)
        while region is not None:
            x, y, w, h = region
            self._api.SetRectangle(x, y, w, h)
            self._api.Recognize(0)
            region = yield self._api.GetUTF8Text()


def average_counter(_m, _n, _x):
    i = _n/(_n+1)
    _m = _m*i + _x/(_n+1)
    return _m, _n+1


if __name__ == '__main__':
    import cv2
    from time import time
    from ctypes import windll
    windll.user32.SetProcessDPIAware()
    m, n = 0, 0
    rl = GameAdaptor('Rocket League (32-bit, DX9, Cooked)')
    rl.start_capture()
    while True:
        t = time()
        image = rl.get_image()
        this = time() - t
        m, n = average_counter(m, n, this)
        txt = rl.get_text((10, 10, 20, 20))
        val = txt.send(None)
        if n % 20 == 0:
            print(round(m*1000, 2))
            cv2.imwrite('tmp/out.png', image)
        cv2.imshow('Rocket League', image)
        cv2.waitKey(30)


