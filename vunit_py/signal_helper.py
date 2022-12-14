from typing import Dict, List, Mapping, Optional, Sequence

from .value import Value, ValueDef
from .test import Test


class SignalHelper(object):
    """
    信号发生器, 时钟无固定周期
    """
    __test: Test
    __inPorts: Dict[str, Dict[int, Value]]
    __outPorts: Dict[str, Dict[int, Value]]
    __initValues: Dict[str, Value]

    def __init__(self, test: Test):
        self.__test = test
        self.__inPorts = {}
        self.__outPorts = {}
        self.__initValues = {}
        for p in test.inPorts:
            self.__inPorts[p] = {}
        for p in test.outPorts:
            self.__outPorts[p] = {}

    def init(self, values: Mapping[str, ValueDef]) -> "SignalHelper":
        """
        设定输入初始值
        """
        for p, v in values.items():
            assert p in self.__inPorts, "输入端口未定义：{}".format(p)
            w = self.__test[p].width
            s = self.__test[p].signed
            if p in self.__initValues:
                raise ValueError("输入端口 {} 已定义初始值：{}".format(
                    p, str(self.__initValues[p])))
            self.__initValues[p] = Value.fromAny(v, w, s)
        return self

    def input(self,
              ts: int,
              values: Mapping[str, ValueDef],
              forceUpdate: bool = False) -> "SignalHelper":
        """
        为某一时间点添加输入
        """
        assert ts > 0, "时钟不是正整数：{}".format(ts)
        for p, v in values.items():
            assert p in self.__inPorts, "输入端口未定义：{}".format(p)
            w = self.__test[p].width
            s = self.__test[p].signed
            if ts in self.__inPorts[p] and not forceUpdate:
                raise ValueError("输入端口 {} 在 {} 已定义输入：{}".format(
                    p, ts, str(self.__inPorts[p][ts])))
            self.__inPorts[p][ts] = Value.fromAny(v, w, s)
        return self

    def output(self,
               ts: int,
               values: Mapping[str, ValueDef],
               forceUpdate: bool = False) -> "SignalHelper":
        """
        为某一时间点添加输出
        """
        assert ts > 0, "时钟不是正整数：{}".format(ts)
        for p, v in values.items():
            assert p in self.__outPorts, "输出端口未定义：{}".format(p)
            w = self.__test[p].width
            s = self.__test[p].signed
            if ts in self.__outPorts[p] and not forceUpdate:
                raise ValueError("输出端口 {} 在 {} 已定义输出：{}".format(
                    p, ts, str(self.__outPorts[p][ts])))
            self.__outPorts[p][ts] = Value.fromAny(v, w, s)
        return self

    def fillOutput(self, port: str, setup_time: int) -> "SignalHelper":
        """
        填充输出
        """
        assert setup_time > 0, "设置时间不是正整数：{}".format(setup_time)
        assert port in self.__outPorts, "输出端口未定义：{}".format(port)
        p = self.__outPorts[port]
        if not p:
            return self
        tss = sorted(p)
        lastTs = tss[0]
        for ts in tss[1:]:
            if ts > lastTs + setup_time:
                p[ts - setup_time] = p[lastTs]
            lastTs = ts
        return self

    def attach(self) -> None:
        """
        将输入/输出添加至测试单元
        """
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


class Cycle:
    interval: int
    offset: int
    ts: Sequence[int]
    setup: Optional[int]

    def __init__(self, interval: int, offset: int, ts: Sequence[int]):
        self.interval = interval
        self.offset = offset
        self.ts = ts
        self.setup = None


class CycleHelper(object):
    """
    信号发生器, 时钟有固定周期
    """
    __test: Test
    __cycles: Dict[str, Cycle]
    __inPorts: Dict[str, Dict[int, List[Value]]]
    __outPorts: Dict[str, Dict[int, List[Value]]]
    __initValues: Dict[str, Value]

    def __init__(self, test: Test):
        self.__test = test
        self.__cycles = {}
        self.__inPorts = {}
        self.__outPorts = {}
        self.__initValues = {}
        for p in test.inPorts:
            self.__inPorts[p] = {}
        for p in test.outPorts:
            self.__outPorts[p] = {}

    def init(self, values: Mapping[str, ValueDef]) -> "CycleHelper":
        """
        设定输入初始值
        """
        for p, v in values.items():
            assert p in self.__inPorts, "输入端口未定义：{}".format(p)
            w = self.__test[p].width
            s = self.__test[p].signed
            if p in self.__initValues:
                raise ValueError("输入端口 {} 已定义初始值：{}".format(
                    p, str(self.__initValues[p])))
            self.__initValues[p] = Value.fromAny(v, w, s)
        return self

    def add(self, port: str, interval: int, offset: int,
            ts: Sequence[int]) -> "CycleHelper":
        """
        为端口添加时钟周期
        """
        assert (port in self.__inPorts
                or port in self.__outPorts), "端口未定义：{}".format(port)
        assert ts, "时间点为空：{}".format(port)
        assert all(ts[i - 1] < ts[i]
                   for i in range(1, len(ts))), "时间点未按升序排列：{}".format(ts)
        mint = ts[0]
        off = offset + mint
        ots = [t - mint for t in ts]
        assert all(0 <= t < interval
                   for t in ots), "时间点越界 [0, {})：{}".format(interval, ts)
        assert port not in self.__cycles, "端口已定义周期：{}".format(port)
        self.__cycles[port] = Cycle(interval, off, ots)
        return self

    def input(self,
              port: str,
              cycle: int,
              values: Sequence[ValueDef],
              forceUpdate: bool = False) -> "CycleHelper":
        """
        为端口的某一周期添加输入
        """
        assert cycle >= 0, "周期数不是非负整数：{}".format(cycle)
        assert port in self.__inPorts, "输入端口未定义：{}".format(port)
        assert port in self.__cycles, "输入端口未定义周期：{}".format(port)
        assert len(values) == len(
            self.__cycles[port].ts), "数据点和时间点数量不匹配：{} != {}".format(
                len(values), len(self.__cycles[port].ts))
        w = self.__test[port].width
        s = self.__test[port].signed
        if cycle in self.__inPorts[port] and not forceUpdate:
            raise ValueError("输入端口 {} 在 {} 已定义输入".format(port, cycle))
        self.__inPorts[port][cycle] = [Value.fromAny(v, w, s) for v in values]
        return self

    def output(self,
               port: str,
               cycle: int,
               values: Sequence[ValueDef],
               forceUpdate: bool = False) -> "CycleHelper":
        """
        为端口的某一周期添加输出
        """
        assert cycle >= 0, "周期数不是非负整数：{}".format(cycle)
        assert port in self.__outPorts, "输出端口未定义：{}".format(port)
        assert port in self.__cycles, "输出端口未定义周期：{}".format(port)
        assert len(values) == len(
            self.__cycles[port].ts), "数据点和时间点数量不匹配：{} != {}".format(
                len(values), len(self.__cycles[port].ts))
        w = self.__test[port].width
        s = self.__test[port].signed
        if cycle in self.__outPorts[port] and not forceUpdate:
            raise ValueError("输出端口 {} 在 {} 已定义输出".format(port, cycle))
        self.__outPorts[port][cycle] = [Value.fromAny(v, w, s) for v in values]
        return self

    def fillOutput(self, port: str, setup_time: int) -> "CycleHelper":
        """
        填充输出
        """
        assert setup_time > 0, "设置时间不是正整数：{}".format(setup_time)
        assert port in self.__outPorts, "输出端口未定义：{}".format(port)
        assert port in self.__cycles, "输出端口未定义周期：{}".format(port)
        self.__cycles[port].setup = setup_time
        return self

    def attach(self) -> None:
        """
        将输入/输出添加至测试单元
        """
        for p, v in self.__initValues.items():
            self.__test[p] // v
        for p, vs in self.__inPorts.items():
            if not vs:
                continue
            assert p in self.__cycles, "输入端口未定义周期：{}".format(p)
            c = self.__cycles[p]
            minc = min(vs)
            maxc = max(vs)
            delta = [c.ts[0] + c.interval - c.ts[-1]
                     ] + [c.ts[i] - c.ts[i - 1] for i in range(1, len(c.ts))]
            self.__test.addEventClock(
                "ec_" + p, delta,
                c.offset + (minc - 1) * c.interval + c.ts[-1])
            self.__test[p]**("ec_" + p)
            lastV = vs[minc][-1]
            for i in range(minc, maxc + 1):
                if i in vs:
                    self.__test[p] << vs[i]
                    lastV = vs[i][-1]
                else:
                    self.__test[p] << [lastV] * len(c.ts)
        for p, vs in self.__outPorts.items():
            if not vs:
                continue
            assert p in self.__cycles, "输出端口未定义周期：{}".format(p)
            c = self.__cycles[p]
            minc = min(vs)
            maxc = max(vs)
            sts = [c.ts[0]]
            split = [False] * len(c.ts)
            for i in range(1, len(c.ts)):
                if c.setup and c.ts[i] - c.setup > c.ts[i - 1]:
                    sts.append(c.ts[i] - c.setup)
                    split[i - 1] = True
                sts.append(c.ts[i])
            if c.setup and c.ts[0] + c.interval - c.setup > c.ts[-1]:
                sts.append(c.ts[0] + c.interval - c.setup)
                split[-1] = True
            delta = [sts[0] + c.interval - sts[-1]
                     ] + [sts[i] - sts[i - 1] for i in range(1, len(sts))]
            self.__test.addEventClock(
                "ec_" + p, delta, c.offset + (minc - 1) * c.interval + sts[-1])
            self.__test[p]**("ec_" + p)
            lastV = vs[minc][-1]
            for i in range(minc, maxc + 1):
                if i in vs:
                    self.__test[p] >> [
                        vs[i][j] for j in range(len(c.ts))
                        for _ in range(2 if split[j] else 1)
                    ]
                    lastV = vs[i][-1]
                elif c.setup:
                    self.__test[p] >> [lastV] * len(sts)
                else:
                    self.__test[p] >> ["x"] * len(sts)
