"""
Lightweight local fallback for ReportLab's rlPyCairo backend.

This project runs on Windows without a system Cairo DLL, so we provide a
drop-in module that uses the already-installable `pycairo` package directly.
The API mirrors the small surface that ReportLab's renderPM backend needs.
"""

__version__ = "0.4.0-local"
__all__ = ("GState", "pil2pict")

import sys

import cairo
from PIL import Image as PILImage
from reportlab.graphics.transform import mmult
from reportlab.lib.colors import toColor


class GState(object):
    __fill_rule_values = (1, 0)

    def __init__(self, width=1, height=1, bg="white", fmt="RGB24"):
        self._fmt = fmt
        self.surface = cairo.ImageSurface(self.__str2format(fmt), width, height)
        self.width = width
        self.height = height
        self.ctx = ctx = cairo.Context(self.surface)
        if fmt == "RGB24":
            self.__set_source_color__ = lambda c: ctx.set_source_rgb(*c.rgb())
        elif fmt == "ARGB32":
            self.__set_source_color__ = lambda c: ctx.set_source_rgba(*c.rgba())
        else:
            raise ValueError("Bad fmt=%r for rlPyCairo.GState" % fmt)
        ctx.set_antialias(cairo.ANTIALIAS_BEST)
        self._in_transform = self._out_transform = (1, 0, 0, -1, 0, height)
        self.ctm = (1, 0, 0, 1, 0, 0)
        self.fillColor = bg
        ctx.rectangle(0, 0, width, height)
        self.pathFill()
        self.pathBegin()
        self.__fillColor = self.__strokeColor = None

        def _text2PathDescription(text, x, y):
            try:
                from reportlab.graphics.utils import FTTextPath, text2PathDescription

                gs = FTTextPath()
            except ImportError:
                try:
                    from _rl_renderPM import gstate
                except ImportError:
                    try:
                        from reportlab.graphics._renderPM import gstate
                    except ImportError as exc:
                        raise ImportError(
                            "freetype-py is not installed and no libart based "
                            "_renderPM can be imported"
                        ) from exc
                from reportlab.graphics.utils import text2PathDescription

                gs = gstate(1, 1)

            def _text2PathDescription(text, x, y):
                return text2PathDescription(
                    text,
                    x=x,
                    y=y,
                    fontName=self.fontName,
                    fontSize=self.fontSize,
                    truncate=False,
                    gs=gs,
                )

            self._text2PathDescription = _text2PathDescription
            return _text2PathDescription(text, x, y)

        self._text2PathDescription = _text2PathDescription
        self.__pathOpMap__ = {
            "moveTo": ctx.move_to,
            "lineTo": ctx.line_to,
            "curveTo": ctx.curve_to,
            "closePath": ctx.close_path,
        }
        self.textRenderMode = 0

    @staticmethod
    def __str2format(fmt):
        return getattr(cairo, "FORMAT_" + fmt)

    @property
    def pixBuf(self):
        ba = self.surface.get_data()
        ba = bytearray(ba)
        if sys.byteorder == "little":
            for i in range(0, len(ba), 4):
                ba[i : i + 3] = bytearray(reversed(ba[i : i + 3]))
        else:
            for i in range(0, len(ba), 4):
                ba[i + 3], ba[i : i + 3] = ba[i], ba[i + 1 : i + 4]
        if self._fmt == "RGB24":
            del ba[3::4]
        return bytes(ba)

    @property
    def ctm(self):
        return mmult(self._out_transform, tuple(self.ctx.get_matrix()))

    @ctm.setter
    def ctm(self, mx):
        nctm = mmult(self._in_transform, mx)
        self.ctx.set_matrix(cairo.Matrix(*nctm))

    @property
    def fillColor(self):
        return self.__fillColor

    @fillColor.setter
    def fillColor(self, c):
        self.__fillColor = toColor(c) if c is not None else c

    @property
    def strokeColor(self):
        return self.__strokeColor

    @strokeColor.setter
    def strokeColor(self, c):
        self.__strokeColor = toColor(c) if c is not None else c

    @property
    def strokeWidth(self):
        return self.ctx.get_line_width()

    @strokeWidth.setter
    def strokeWidth(self, w):
        return self.ctx.set_line_width(w)

    @property
    def dashArray(self):
        return self.ctx.get_dash()

    @dashArray.setter
    def dashArray(self, da):
        if not da or not isinstance(da, (list, tuple)):
            da = 0, ()
        else:
            if isinstance(da[0], (list, tuple)):
                da = da[1], da[0]

        return self.ctx.set_dash(da[1], da[0])

    @property
    def lineCap(self):
        return int(self.ctx.get_line_cap())

    @lineCap.setter
    def lineCap(self, v):
        return self.ctx.set_line_cap(int(v))

    @property
    def lineJoin(self):
        return int(self.ctx.get_line_join())

    @lineJoin.setter
    def lineJoin(self, v):
        return self.ctx.set_line_join(int(v))

    @property
    def fillMode(self):
        return self.__fill_rule_values[int(self.ctx.get_fill_rule())]

    @fillMode.setter
    def fillMode(self, v):
        return self.ctx.set_fill_rule(self.__fill_rule_values[int(v)])

    def beginPath(self):
        self.ctx.new_path()

    def moveTo(self, x, y):
        self.ctx.move_to(float(x), float(y))

    def lineTo(self, x, y):
        self.ctx.line_to(float(x), float(y))

    def pathClose(self):
        self.ctx.close_path()

    def pathFill(self, fillMode=None):
        if self.__fillColor:
            if fillMode is not None:
                old_fill_mode = self.fillMode
                if old_fill_mode != fillMode:
                    self.fillMode = fillMode
            self.__set_source_color__(self.__fillColor)
            self.ctx.fill_preserve()
            if fillMode is not None and old_fill_mode != fillMode:
                self.fillMode = old_fill_mode

    def pathStroke(self):
        if self.__strokeColor and self.strokeWidth > 0:
            self.__set_source_color__(self.__strokeColor)
            self.ctx.stroke_preserve()

    def curveTo(self, x1, y1, x2, y2, x3, y3):
        self.ctx.curve_to(
            float(x1),
            float(y1),
            float(x2),
            float(y2),
            float(x3),
            float(y3),
        )

    def pathBegin(self):
        self.ctx.new_path()

    def clipPathClear(self):
        self.ctx.reset_clip()

    def clipPathSet(self):
        ctx = self.ctx
        old_path = ctx.copy_path()
        ctx.clip()
        ctx.new_path()
        ctx.append_path(old_path)

    def clipPathAdd(self):
        self.ctx.clip_preserve()

    def setFont(self, fontName, fontSize):
        self.fontName = fontName
        self.fontSize = fontSize

    def drawString(self, x, y, text):
        op_map = self.__pathOpMap__
        old_path = self.ctx.copy_path()
        old_fill_mode = self.fillMode
        text_render_mode = self.textRenderMode
        try:
            self.ctx.new_path()
            for op in self._text2PathDescription(text, x, y):
                op_map[op[0]](*op[1:])
            if text_render_mode in (0, 2, 4, 6):
                self.pathFill(0)
            if text_render_mode in (1, 2, 5, 6):
                self.pathStroke()
            if text_render_mode >= 4:
                self.ctx.clip_preserve()
        finally:
            self.ctx.new_path()
            self.ctx.append_path(old_path)
            self.fillMode = old_fill_mode

    @classmethod
    def __fromPIL(cls, im, fmt="RGB24", alpha=1.0, forceAlpha=False):
        mode = im.mode
        im = im.copy()
        argb = fmt == "ARGB32"
        if mode == "RGB":
            im.putalpha(int(alpha * 255))
            if alpha != 1 and argb:
                im = im.convert("RGBa")
        elif mode == "RGBA" or forceAlpha:
            if forceAlpha:
                im.putalpha(int(alpha * 255))
            if argb:
                im = im.convert("RGBa")
        elif mode == "RGBa" or forceAlpha:
            if forceAlpha:
                im = im.convert("RGBA")
                im.putalpha(int(alpha * 255))
                if argb:
                    im = im.convert("RGBa")
        fmt = cls.__str2format(fmt)
        if sys.byteorder == "little":
            ba = im.tobytes("raw", "BGRa")
        else:
            ba = bytearray(im.tobytes("raw", "RGBa"))
            for i in range(0, len(ba), 4):
                ba[i], ba[i + 1 : i + 4] = ba[i + 3], ba[i : i + 3]
            ba = bytes(ba)
        return cairo.ImageSurface.create_for_data(
            bytearray(ba),
            fmt,
            im.width,
            im.height,
            cairo.ImageSurface.format_stride_for_width(fmt, im.width),
        )

    def _aapixbuf(self, x, y, dstW, dstH, data, srcW, srcH, planes=3):
        ctx = self.ctx
        ctx.save()
        ctx.set_antialias(cairo.ANTIALIAS_DEFAULT)
        ctx.set_operator(cairo.OPERATOR_OVER)
        ctx.translate(x, y + dstH)
        ctx.scale(dstW / float(srcW), -dstH / float(srcH))
        ctx.set_source_surface(self.__fromPIL(data, self._fmt, forceAlpha=False))
        ctx.paint()
        ctx.restore()


headerLen = 512
maxLen = 127
picVersion = 0x11
background = 0x1B
headerOp = 0x0C00
clipRgn = 0x01
PackBitsRect = 0x98
EndOfPicture = 0xFF
MAXCOLORS = 256


def pil2pict(cols, rows, pixels, palette, tc=-1):
    from io import BytesIO
    from struct import pack as struct_pack

    colors = len(palette)
    buffer = BytesIO()

    def putc(c):
        buffer.write(c)

    def putFill(n):
        buffer.write(n * b"\x00")

    def putShort(v):
        buffer.write(struct_pack(">H", v))

    def putLong(v):
        buffer.write(struct_pack(">l", v))

    def putRect(s0, s1, s2, s3):
        putShort(s0)
        putShort(s1)
        putShort(s2)
        putShort(s3)

    colors //= 3

    putFill(headerLen)
    putShort(0)
    putRect(0, 0, rows, cols)
    putShort(picVersion)
    putShort(0x02FF)
    putShort(headerOp)
    putLong(-1)
    putRect(72, 0, 72, 0)
    putRect(cols, 0, rows, 0)
    putFill(4)
    putShort(0x1E)
    putShort(clipRgn)
    putShort(10)
    putRect(0, 0, rows, cols)
    if tc != -1:
        putShort(background)
        putShort((((tc >> 16) & 0xFF) * 65535) // 255)
        putShort((((tc >> 8) & 0xFF) * 65535) // 255)
        putShort(((tc & 0xFF) * 65535) // 255)
        putShort(5)
        putShort(36 | 64)
        putShort(8)
        putShort(36 | 64)

    putShort(PackBitsRect)
    putShort(cols | 0x8000)
    putRect(0, 0, rows, cols)
    putShort(0)
    putShort(0)
    putLong(0)
    putRect(72, 0, 72, 0)
    putShort(0)
    putShort(8)
    putShort(1)
    putShort(8)
    putLong(0)
    putLong(0)
    putLong(0)
    putLong(0)
    putShort(0)
    putShort(colors - 1)

    for i in range(colors):
        putShort(i)
        putShort((palette[3 * i] * 65535) // 255)
        putShort((palette[3 * i + 1] * 65535) // 255)
        putShort((palette[3 * i + 2] * 65535) // 255)

    putRect(0, 0, rows, cols)
    putRect(0, 0, rows, cols)
    putShort((36 | 64) if tc != -1 else 0)

    row_data = bytearray()
    run = bytearray()
    run_append = run.append
    run_extend = run.extend
    run_reverse = run.reverse
    cols1 = cols - 1
    if cols >= 250:
        putRLen = putShort
        rli = 2
    else:
        putRLen = lambda c: putc(bytes([c]))
        rli = 1

    rtc = lambda c: 257 - c
    ctc = lambda c: c - 1

    for j0 in range(0, rows * cols, cols):
        row_data[:] = pixels[j0 : j0 + cols]
        run[:] = bytearray()
        k = 0
        while k <= cols1:
            p = row_data[k]
            k1 = k + 1
            while k1 <= cols1 and row_data[k1] == p and k1 - k < maxLen:
                k1 += 1
            if k1 - k > 1:
                run_append(rtc(k1 - k))
                run_append(p)
                k = k1
            else:
                start = k
                k += 1
                while k <= cols1:
                    p = row_data[k]
                    k1 = k + 1
                    while k1 <= cols1 and row_data[k1] == p and k1 - k < maxLen:
                        k1 += 1
                    if k1 - k > 1 or k - start >= maxLen:
                        break
                    k += 1
                run_append(ctc(k - start))
                run_extend(row_data[start:k])

        putRLen(len(run))
        if rli == 2:
            if len(run) & 1:
                run_append(0)
        run_reverse()
        while run:
            putc(bytes([run.pop()]))

    if buffer.tell() & 1:
        putc(b"\x00")
    putShort(EndOfPicture)
    data = buffer.getvalue()
    return data[:512] + struct_pack(">H", len(data) - 512) + data[514:]
