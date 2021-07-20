import typing
from typing import Iterator, List, Sequence, Union
from enum import Enum


class Logic(Enum):
    """
    一位逻辑值 0/1/x/z
    """
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
        """
        从单个字符转换为逻辑值
        """
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
    """
    值, 包含多位逻辑值
    """
    __value: List[Logic]
    __signed: bool

    def __init__(self, value: Sequence[Logic], signed: bool):
        """
        value: 逻辑值序列
        signed: 值是否有符号, 对应 verilog 中 signed
        """
        assert value, "值为空"
        assert not signed or len(value) >= 2, "有符号值少于 2 位"
        self.__value = list(value)
        self.__signed = signed

    def __str__(self) -> str:
        return "".join([str(v) for v in self.__value])

    def __repr__(self) -> str:
        return str(self)

    def __int__(self) -> int:
        assert all([v == Logic.LO or v == Logic.HI
                    for v in self.__value]), "包含 x 或 z 的值无法转换为整数"
        res = 0
        for v in self.__value:
            res <<= 1
            res |= 1 if v == Logic.HI else 0
        return res if not self.__signed else res - (1 << len(self.__value))

    def __iter__(self) -> Iterator[Logic]:
        return iter(self.__value)

    @typing.overload
    def __getitem__(self, i: int) -> Logic:
        ...

    @typing.overload
    def __getitem__(self, i: slice) -> "Value":
        ...

    def __getitem__(self, i: Union[int, slice]):
        assert not self.__signed, "有符号值无法分割"
        if isinstance(i, slice):
            return Value(self.__value[i], False)
        return self.__value[i]

    @property
    def value(self) -> List[Logic]:
        """
        以列表形式表示的值
        """
        return self.__value

    @property
    def width(self) -> int:
        """
        值宽度
        """
        return len(self.__value)

    @property
    def signed(self) -> bool:
        """
        值是否有符号
        """
        return self.__signed

    def slice(self, width: int, signed: bool) -> List["Value"]:
        """
        width: 宽度
        signed: 新的值是否有符号

        将当前值按宽度分割为新的值序列, 当前值必须无符号
        """
        assert not self.__signed, "有符号值无法分割"
        assert width > 0, "分割宽度不是正整数"
        assert self.width % width == 0, "宽度不是倍数，无法分割：{} | {}".format(
            self.width, width)
        return [
            Value(self.__value[i * width:(i + 1) * width], signed)
            for i in range(self.width // width)
        ]

    @staticmethod
    def fromBools(bs: Sequence[bool], width: int) -> "Value":
        """
        bs: 布尔序列
        width: 宽度

        从布尔序列生成值, 无符号
        """
        assert width > 0, "宽度不是正整数"
        assert len(bs) == width, "值的宽度不匹配：{} != {}".format(len(bs), width)
        return Value([Logic.HI if b else Logic.LO for b in bs], False)

    @staticmethod
    def fromInt(v: int, width: int, signed: bool) -> "Value":
        """
        v: 整数值
        width: 宽度
        signed: 值是否有符号

        从整数生成值
        """
        assert width > 0, "宽度不是正整数"
        if signed:
            assert width > 1, "有符号值宽度小于 2"
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
        ], signed)

    @staticmethod
    def fromStr(s: str, width: int, signed: bool) -> "Value":
        """
        s: 字符串
        width: 宽度
        signed: 值是否有符号

        从字符串生成值, "x" 表示所有位都是 x, "z" 表示所有位都是 z
        """
        assert width > 0, "宽度不是正整数"
        if s.lower() == "x":
            return Value([Logic.X] * width, signed)
        if s.lower() == "z":
            return Value([Logic.Z] * width, signed)
        assert len(s) == width, "值的宽度不匹配：{} != {}".format(len(s), width)
        return Value([Logic.fromChar(c) for c in s], signed)

    @staticmethod
    def fromBytes(s: bytes, width: int, signed: bool) -> "Value":
        """
        s: 字节序列
        width: 宽度
        signed: 值是否有符号

        从字节序列生成值
        """
        assert width > 0, "宽度不是正整数"
        assert len(s) * 8 == width, "值的宽度不匹配：{} != {}".format(
            len(s) * 8, width)
        return Value([v for c in s for v in Value.fromInt(c, 8, False)],
                     signed)

    @staticmethod
    def fromAny(v: "ValueDef", width: int, signed: bool) -> "Value":
        """
        v: ValueDef 中包含的任意类型
        width: 宽度
        signed: 值是否有符号

        从任意类型生成值
        """
        if isinstance(v, Value):
            msg = "值的宽度不匹配：{} != {}".format(v.width, width)
            assert v.width == width, msg
            msg = "值的符号不匹配：{} != {}".format("有符号" if v.signed else "无符号",
                                            "有符号" if signed else "无符号")
            assert v.signed == signed, msg
            return v
        if isinstance(v, str):
            return Value.fromStr(v, width, signed)
        if isinstance(v, bytes):
            return Value.fromBytes(v, width, signed)
        if isinstance(v, int):
            return Value.fromInt(v, width, signed)
        return Value.fromBools(v, width)


ValueDef = Union[Value, int, str, bytes, Sequence[bool]]
