from typing import List, Mapping, Optional, Protocol, Sequence, Union
from abc import abstractmethod
from enum import Enum

from .value import Value


class PortType(Enum):
    """
    端口类型, 输入/输出
    """
    IN = 1
    OUT = 2


ValueDef = Union[Value, int, str, bytes]
SignalDef = Union[Sequence[ValueDef], Mapping[int, ValueDef], bytes]


class EventClockContainerProtocol(Protocol):
    @abstractmethod
    def hasClock(self, clk: str) -> bool:
        raise NotImplementedError()


class Port:
    """
    输入/输出端口
    """
    __portType: PortType
    __width: int
    __signed: bool
    __clk: str
    __initValue: Optional[Value]
    __seq: List[Value]
    __parent: EventClockContainerProtocol

    def __init__(self, portType: PortType, width: int, signed: bool,
                 parent: EventClockContainerProtocol):
        """
        portType: 端口类型, 输入/输出
        width: 端口宽度
        signed: 端口是否有符号, 对应 verilog 定义中是否包含 signed
        parent: 一般为 Test
        """
        assert width > 0, "端口宽度不为正：{}".format(width)
        self.__portType = portType
        self.__width = width
        self.__signed = signed
        self.__clk = ""
        self.__initValue = None
        self.__seq = []
        self.__parent = parent

    @property
    def portType(self) -> PortType:
        """
        端口类型
        """
        return self.__portType

    @property
    def width(self) -> int:
        """
        端口宽度
        """
        return self.__width

    @property
    def signed(self) -> bool:
        """
        端口是否有符号
        """
        return self.__signed

    @property
    def clk(self) -> str:
        """
        端口依附的事件时钟名
        """
        return self.__clk

    @property
    def initValue(self) -> Optional[Value]:
        """
        端口输入初始值
        """
        assert self.portType == PortType.IN
        return self.__initValue

    @property
    def input(self) -> Sequence[Value]:
        """
        端口输入
        """
        assert self.portType == PortType.IN
        return self.__seq

    @property
    def output(self) -> Sequence[Value]:
        """
        端口输出
        """
        assert self.portType == PortType.OUT
        return self.__seq

    def __pow__(self, clk: str) -> "Port":
        """
        将端口依附于事件时钟 clk
        """
        assert clk, "事件时钟为空"
        assert not self.__clk, "端口已依附于事件时钟 {}".format(self.__clk)
        assert self.__parent.hasClock(clk), "事件时钟不存在：{}".format(clk)
        self.__clk = clk
        return self

    def normalize(self, signal: SignalDef) -> Sequence[Value]:
        """
        将信号 signal 规范化为值序列

        当 signal 为 bytes 时, 按端口宽度将信号分割为值序列
        当 signal 为字典类型时, 按序号扩充为值序列。对于输入，填充之前的值，对于输出，填充 x
        当 signal 为列表类型时, 直接返回
        """
        if isinstance(signal, bytes):
            msg = "使用字节形式表达信号序列时，端口宽度不为 2 的幂次：{}".format(self.width)
            assert (self.width & (self.width - 1)) == 0, msg
            if self.width > 8:
                msg = "使用字节形式表达信号序列时，序列长度不是端口宽度的倍数：{} | {}".format(
                    len(signal) * 8, self.width)
                assert (len(signal) % (self.width / 8) == 0), msg
            return Value.fromBytes(signal,
                                   len(signal) * 8,
                                   False).slice(self.width, self.signed)
        elif isinstance(signal, Mapping):
            vs = sorted(
                [(t, Value.fromAny(x, self.width, self.signed))
                 for t, x in signal.items()],
                key=lambda x: x[0],
            )
            msg = "使用字典形式表达信号序列时，指定的序号小于当前序列长度：{} < {}".format(
                vs[0][0], len(self.__seq))
            assert vs[0][0] >= len(self.__seq), msg
            if self.portType == PortType.OUT:
                values = [Value.fromStr("x", self.width, self.signed)
                          ] * (vs[-1][0] + 1 - len(self.output))
                for t, v in vs:
                    values[t - len(self.output)] = v
            else:
                lastT = len(self.input) - 1
                lastV = (self.input[-1] if self.input else
                         self.initValue if self.initValue else Value.fromStr(
                             "x", self.width, self.signed))
                values = []
                for t, v in vs:
                    values += [lastV] * (t - lastT - 1)
                    values.append(v)
                    lastT = t
                    lastV = v
            return values
        else:
            return [Value.fromAny(x, self.width, self.signed) for x in signal]

    def __floordiv__(self, input: ValueDef) -> "Port":
        """
        设定端口输入初始值
        """
        assert self.portType == PortType.IN, "输出端口不可定义初始值"
        assert not self.__seq, "定义输入序列后，不可定义初始值"
        v = Value.fromAny(input, self.width, self.signed)
        msg = "输入初始值宽度不匹配：{} != {}".format(v.width, self.width)
        assert v.width == self.width, msg
        self.__initValue = v
        return self

    def __lshift__(self, input: SignalDef) -> "Port":
        """
        添加端口输出
        """
        assert self.portType == PortType.IN, "输出端口不可定义输入（输出定义方式为 >>）"
        self.__seq += self.normalize(input)
        return self

    def __rshift__(self, output: SignalDef) -> "Port":
        """
        添加端口输入
        """
        assert self.portType == PortType.OUT, "输入端口不可定义输出（输入定义方式为 <<）"
        self.__seq += self.normalize(output)
        return self
