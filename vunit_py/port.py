from typing import Dict, List, Protocol, Union
from abc import abstractmethod
from enum import Enum

from .value import Logic, Value


class PortType(Enum):
    IN = 1
    OUT = 2


ValueDef = Union[Value, int, str, bytes]
SignalDef = Union[List[ValueDef], Dict[int, ValueDef], bytes]


class EventClockContainerProtocol(Protocol):
    @abstractmethod
    def hasClock(self, clk: str) -> bool:
        raise NotImplementedError()


class Port(object):
    portType: PortType
    width: int
    signed: bool
    _clk: str
    _initValue: Value
    _input: List[Value]
    _output: List[Value]
    __parent: EventClockContainerProtocol

    def __init__(self, portType: PortType, width: int, signed: bool,
                 parent: EventClockContainerProtocol):
        assert width > 0, "端口宽度不为正：{}".format(width)
        self.portType = portType
        self.width = width
        self.signed = signed
        self.__parent = parent
        if portType == PortType.IN:
            self._input = []
        elif portType == PortType.OUT:
            self._output = []

    def __pow__(self, clk: str) -> "Port":
        assert self.__parent.hasClock(clk), "事件时钟不存在：{}".format(clk)
        self._clk = clk
        return self

    def normalize(self, input: SignalDef) -> List[Value]:
        if isinstance(input, bytes):
            assert (
                self.width &
                (self.width - 1)) == 0, "使用字节形式表达信号序列时，端口宽度不为 2 的幂次：{}".format(
                    self.width)
            if self.width > 8:
                assert len(input) % (
                    self.width /
                    8) == 0, "使用字节形式表达信号序列时，序列长度不是端口宽度的倍数：{} | {}".format(
                        len(input) * 8, self.width)
            return Value.fromBytes(input, len(input) * 8).slice(self.width)
        elif isinstance(input, dict):
            vs = sorted([(t, Value.fromAny(x, self.width, self.signed))
                         for t, x in input.items()],
                        key=lambda x: x[0])
            if self.portType == PortType.OUT:
                assert vs[0][0] >= len(
                    self._output
                ), "使用字典形式表达信号序列时，指定的时间小于当前序列长度：{} < {}".format(
                    vs[0][0], len(self._output))
                values = [Value.fromStr("x", self.width)
                          ] * (vs[-1][0] + 1 - len(self._output))
                for t, v in vs:
                    values[t - len(self._output)] = v
            else:
                assert vs[0][0] >= len(
                    self._input), "使用字典形式表达信号序列时，指定的时间小于当前序列长度：{} < {}".format(
                        vs[0][0], len(self._output))
                lastT = len(self._input) - 1
                lastV = self._input[
                    -1] if self._input else self._initValue if hasattr(
                        self, "_initValue") and self._initValue else Value(
                            [Logic.X] * self.width)
                values = []
                for t, v in vs:
                    values += [lastV] * (t - lastT - 1)
                    values.append(v)
                    lastT = t
                    lastV = v
            return values
        else:
            return [Value.fromAny(x, self.width, self.signed) for x in input]

    def __floordiv__(self, input: ValueDef) -> "Port":
        assert self.portType == PortType.IN, "输出端口不可定义初始值"
        assert not self._input, "定义输入序列后，不可定义初始值"
        self._initValue = Value.fromAny(input, self.width, self.signed)
        return self

    def __lshift__(self, input: SignalDef) -> "Port":
        assert self.portType == PortType.IN, "输出端口不可定义输入（输出定义方式为 >>）"
        self._input += self.normalize(input)
        return self

    def __rshift__(self, output: SignalDef) -> "Port":
        assert self.portType == PortType.OUT, "输入端口不可定义输出（输入定义方式为 <<）"
        self._output += self.normalize(output)
        return self
