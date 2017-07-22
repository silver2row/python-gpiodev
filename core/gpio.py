import ctypes
import ctypes.util
import os


########################################################
# Constants from linux/gpio.h
########################################################

GPIOHANDLES_MAX = 64

GPIOHANDLE_REQUEST_INPUT = 1 << 0
GPIOHANDLE_REQUEST_OUTPUT = 1 << 1
GPIOHANDLE_REQUEST_ACTIVE_LOW = 1 << 2
GPIOHANDLE_REQUEST_OPEN_DRAIN = 1 << 3
GPIOHANDLE_REQUEST_OPEN_SOURCE = 1 << 4

########################################################
# ctypes structures
########################################################

libgpioctl = ctypes.CDLL(
    os.path.join(
        os.path.dirname(__file__),
        'libgpioctl.so.0.0.1',
    )
)

c32 = ctypes.c_char * 32

cul_MAX = ctypes.c_ulong * GPIOHANDLES_MAX
cu8_MAX = ctypes.c_ubyte * GPIOHANDLES_MAX


class _gpiochip_info (ctypes.Structure):
    _fields_ = [
        ("name", c32),
        ("label", c32),
        ("lines", ctypes.c_long),
    ]


class _gpioline_info (ctypes.Structure):
    _fields_ = [
        ("line", ctypes.c_long),
        ("flags", ctypes.c_ulong),
        ("name", c32),
        ("consumer", c32),
    ]


class _gpiohandle_request (ctypes.Structure):
    _fields_ = [
        ('lineoffsets', cul_MAX),
        ('flags', ctypes.c_ulong),
        ('default_values', cu8_MAX),
        ('consumer_label', c32),
        ('lines', ctypes.c_ulong),
        ('fd', ctypes.c_int),
    ]


class _gpioevent_request (ctypes.Structure):
    _fields_ = [
        ('lineoffset', ctypes.c_ulong),
        ('handleflags', ctypes.c_ulong),
        ('eventflags', ctypes.c_ulong),
        ('consumer_label', c32),
        ('fd', ctypes.c_int),
    ]


class _gpiohandle_data (ctypes.Structure):
    _fields_ = [
        ('values', cu8_MAX),
    ]

########################################################


class GPIOError(IOError):
    pass


class _GPIOChip():

    def __init__(self, path):
        self.path = path

        self.fd = os.open(self.path, os.O_RDWR)

    def info(self):
        _info = _gpiochip_info()
        status = libgpioctl.get_chipinfo(self.fd, ctypes.byref(_info))
        if status != 0:
            raise GPIOError("get_chipinfo call returned non-zero status")

        info = {
            "name": _info.name,
            "label": _info.label,
            "lines": _info.lines,
            }

        return info

    def line_info(self, line):
        _info = _gpioline_info(line=line)

        status = libgpioctl.get_lineinfo(self.fd, ctypes.byref(_info))
        if status != 0:
            raise GPIOError("get_chipinfo call returned non-zero status")

        info = {
            "line": _info.line,
            "flags": _info.flags,
            "name": _info.name,
            "consumer": _info.consumer,
        }

        return info


_GPIO = _GPIOChip("/dev/gpiochip0")


class GPIOHandle:

    _FLAGS = {
        'out': GPIOHANDLE_REQUEST_OUTPUT,
        'in': GPIOHANDLE_REQUEST_INPUT,
    }

    def __init__(
            self,
            lines,
            mode,
            defaults=None,
            label=b'',
            GPIO=_GPIO,
    ):
        self.num_lines = len(lines)

        if self.num_lines > GPIOHANDLES_MAX:
            raise GPIOError(
                "Can not create handle: "
                "number of lines {0} exceeds the limit ({1})"
                .format(self.num_lines, GPIOHANDLES_MAX)
            )

        self.flags = self._FLAGS.get(mode, mode)

        if not defaults:
            defaults = (0,) * self.num_lines

        self.defaults = defaults
        self.lines = lines
        self.label = label
        self.gpio = GPIO

        _request = _gpiohandle_request(
            lineoffsets=self.lines,
            flags=self.flags,
            default_values=self.defaults,
            consumer_label=self.label,
            lines=self.num_lines,
        )

        status = libgpioctl.get_linehandle(
            self.gpio.fd,
            ctypes.byref(_request),
        )

        if status != 0:
            raise GPIOError("get_linehandle call returned non-zero status")

        self.handle = _request.fd

    def set_values(self, values):
        if len(values) != self.num_lines:
            raise GPIOError(
                "Number of values {0} doesn't match number of lines {1}"
                .format(len(values), self.num_lines)
            )

        if self.flags & GPIOHANDLE_REQUEST_OUTPUT == 0:
            raise GPIOError("Can not set values, as we are not in output mode")

        _data = _gpiohandle_data(values)
        status = libgpioctl.set_line_values(self.handle, ctypes.byref(_data))
        if status != 0:
            raise GPIOError("set_line_values call returned non-zero status")

    def get_values(self):
        _data = _gpiohandle_data()
        status = libgpioctl.get_line_values(self.handle, ctypes.byref(_data))
        if status != 0:
            raise GPIOError("get_line_values call returned non-zero status")

        return _data.values[:self.num_lines]