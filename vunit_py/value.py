import typing
from typing import Iterator, Sequence, Union
from enum import Enum


class Logic(Enum):
    LO = 0
    HI = 1
    X = 2
    Z = 3

    def __str__(self) -> str:
        if self.value == 0:
            return "0"
        elif self.value == 1:
            return "1"
        elif self.value == 2:
            return "x"
        elif self.value == 3:
            return "z"
        assert False, "值非法：{}".format(self.value)

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def fromChar(c: str) -> "Logic":
        if c == "0":
            return Logic.LO
        elif c == "1":
            return Logic.HI
        elif c == "x" or c == "X":
            return Logic.X
        elif c == "z" or c == "Z":
            return Logic.Z
        assert False, "值包含非法字符：{}".format(c)


class Value(object):
    value: Sequence[Logic]

    def __init__(self, value: Sequence[Logic]):
        self.value = value

    def __len__(self) -> int:
        return len(self.value)

    def __str__(self) -> str:
        return "".join([str(v) for v in self.value])

    def __repr__(self) -> str:
        return str(self)

    def __int__(self) -> int:
        assert all([v == Logic.LO or v == Logic.HI
                    for v in self.value]), "包含 x 或 z 的值无法转换为整数"
        res = 0
        for v in self.value:
            res <<= 1
            res |= 1 if v == Logic.HI else 0
        return res

    def __bool__(self) -> bool:
        return bool(self.value)

    def __iter__(self) -> Iterator[Logic]:
        return iter(self.value)

    @typing.overload
    def __getitem__(self, i: int) -> Logic:
        ...

    @typing.overload
    def __getitem__(self, i: slice) -> "Value":
        ...

    def __getitem__(self, i):
        if isinstance(i, slice):
            return Value(self.value[i])
        return self.value[i]

    def slice(self, width: int) -> Sequence["Value"]:
        assert width > 0, "分割宽度不是正整数"
        assert len(self) % width == 0, "宽度不是倍数，无法分割：{} | {}".format(
            len(self), width)
        return [
            Value(self.value[i * width:(i + 1) * width])
            for i in range(len(self) // width)
        ]

    @staticmethod
    def fromBools(bs: Sequence[bool], width: int) -> "Value":
        assert width > 0, "宽度不是正整数"
        assert len(bs) == width, "值的宽度不匹配：{} != {}".format(len(bs), width)
        return Value([Logic.HI if b else Logic.LO for b in bs])

    @staticmethod
    def fromInt(v: int, width: int, signed: bool) -> "Value":
        assert width > 0, "宽度不是正整数"
        if signed:
            assert width > 1, "有符号整数宽度小于 2"
            lim = 1 << (width - 1)
            assert v >= -lim, "有符号值宽度太大：{} < 2^{}".format(v, width - 1)
            assert v < lim, "有符号值宽度太大：{} >= 2^{}".format(v, width - 1)
            v = v % (1 << width)
        else:
            assert v >= 0, "不支持负数值"
            assert v < (1 << width), "值宽度太大：{} >= 2^{}".format(v, width)
        return Value([
            Logic.HI if (v >> (width - 1 - i)) & 1 else Logic.LO
            for i in range(width)
        ])

    @staticmethod
    def fromStr(s: str, width: int) -> "Value":
        assert width > 0, "宽度不是正整数"
        if s.lower() == "x":
            return Value([Logic.X] * width)
        assert len(s) == width, "值的宽度不匹配：{} != {}".format(len(s), width)
        return Value([Logic.fromChar(c) for c in s])

    @staticmethod
    def fromBytes(s: bytes, width: int) -> "Value":
        assert width > 0, "宽度不是正整数"
        assert len(s) * 8 == width, "值的宽度不匹配：{} != {}".format(
            len(s) * 8, width)
        return Value([v for c in s for v in Value.fromInt(c, 8, False)])

    @staticmethod
    def fromAny(input: "ValueDef", width: int, signed: bool) -> "Value":
        if isinstance(input, Value):
            assert len(input) == width, "值的宽度不匹配：{} != {}".format(
                len(input), width)
            return input
        if isinstance(input, str):
            return Value.fromStr(input, width)
        if isinstance(input, bytes):
            return Value.fromBytes(input, width)
        if isinstance(input, int):
            return Value.fromInt(input, width, signed)
        return Value.fromBools(input, width)


ValueDef = Union[Value, int, str, bytes, Sequence[bool]]
