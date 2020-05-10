from typing import Dict, Union
import logging

from .value import Value
from .test import Test

ValueDef = Union[Value, int, str, bytes]


class SignalHelper(object):
    __test: Test
    __inPorts: Dict[str, Dict[int, Value]]
    __outPorts: Dict[str, Dict[int, Value]]
    __initValues: Dict[str, Value]

    def __init__(self, test: Test):
        self.__test = test
        self.__inPorts = {}
        self.__outPorts = {}
        self.__initValues = {}
        for p in test._inPorts:
            self.__inPorts[p] = {}
        for p in test._outPorts:
            self.__outPorts[p] = {}

    def init(self, values: Dict[str, ValueDef]) -> None:
        for p, v in values.items():
            assert p in self.__inPorts, "输入端口未定义：{}".format(p)
            w = self.__test[p].width
            if p in self.__initValues:
                logging.warning("输入端口 {} 已定义初始值：{}".format(
                    p, str(self.__initValues[p])))
            self.__initValues[p] = Value.fromAny(v, w)

    def input(self, ts: int, values: Dict[str, ValueDef]) -> None:
        assert ts > 0, "时钟不是正整数：{}".format(ts)
        for p, v in values.items():
            assert p in self.__inPorts, "输入端口未定义：{}".format(p)
            w = self.__test[p].width
            if ts in self.__inPorts[p]:
                logging.warning("输入端口 {} 在 {} 已定义输入：{}".format(
                    p, ts, str(self.__inPorts[p][ts])))
            self.__inPorts[p][ts] = Value.fromAny(v, w)

    def output(self, ts: int, values: Dict[str, ValueDef]) -> None:
        assert ts > 0, "时钟不是正整数：{}".format(ts)
        for p, v in values.items():
            assert p in self.__outPorts, "输出端口未定义：{}".format(p)
            w = self.__test[p].width
            if ts in self.__outPorts[p]:
                logging.warning("输出端口 {} 在 {} 已定义输入：{}".format(
                    p, ts, str(self.__outPorts[p][ts])))
            self.__outPorts[p][ts] = Value.fromAny(v, w)

    def attach(self) -> None:
        for p, v in self.__initValues.items():
            self.__test[p] // v
        for p, vs in self.__inPorts.items():
            if not vs:
                continue
            ts = sorted(vs)
            dts = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
            self.__test.addEventClock("ec_" + p, ts[:1] + dts)
            self.__test[p]**("ec_" + p) << [vs[t] for t in ts]
        for p, vs in self.__outPorts.items():
            if not vs:
                continue
            ts = sorted(vs)
            dts = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
            self.__test.addEventClock("ec_" + p, ts[:1] + dts)
            self.__test[p]**("ec_" + p) >> [vs[t] for t in ts]
