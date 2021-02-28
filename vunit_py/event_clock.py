from typing import Sequence


class EventClock:
    """
    事件时钟
    """
    __steps: Sequence[int]
    __ts: Sequence[int]
    __prelude: Sequence[int]
    __offset: int

    def __init__(self, steps: Sequence[int], offset: int):
        """
        steps: 时钟步长, 即一个完整周期之内的时间点之间的间隔
        offset: 时钟偏移, 即第一个完整周期相对于零点的偏移

          假设 steps = [2, 3], offset = 5, 则第一个完整周期为 (5, 10],
        包括两个时间点 5 + 2 = 7 和 5 + 2 + 3 = 10
          假设 steps = [2, 3], offset = -3, 则理论上第一个完整周期为 (-3, 2],
        包括两个时间点 -3 + 2 = -1 和 -3 + 2 + 3 = 2, 但是零点及之前的时间点需要舍弃,
        因此只保留时间点 2
        """
        assert steps, "事件时钟为空"
        assert all([isinstance(s, int) and s > 0
                    for s in steps]), "事件时钟步长不是正整数"
        ts = [steps[0]]
        for t in steps[1:]:
            ts.append(ts[-1] + t)
        self.__steps = steps
        self.__ts = ts
        if offset >= 0:
            self.__offset = offset
            self.__prelude = []
        else:
            self.__offset = offset % -sum(self.__steps)
            self.__prelude = [t + offset for t in ts if t + offset > 0]

    @property
    def steps(self) -> Sequence[int]:
        """
        时钟步长
        """
        return self.__steps

    @property
    def ts(self) -> Sequence[int]:
        """
        每个时钟周期之内的时间点（相对周期起点）
        """
        return self.__ts

    @property
    def offset(self) -> int:
        """
        时钟偏移
        """
        return self.__offset

    @property
    def prelude(self) -> Sequence[int]:
        """
        第一个完整周期之前的时间点（相对零点）
        """
        return self.__prelude

    def __getitem__(self, t: int) -> int:
        """
        序号 t 所对应的时间点
        """
        if self.offset >= 0:
            s = self.offset
        else:
            if t < len(self.prelude):
                return self.prelude[t]
            s = self.prelude[-1]
            t -= len(self.prelude)
        n = len(self.ts)
        return s + t // n * self.ts[-1] + self.ts[t % n]
