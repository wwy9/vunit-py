from typing import Sequence


class EventClock(object):
    _steps: Sequence[int]
    _offset: int

    def __init__(self, steps: Sequence[int], offset: int):
        assert all([isinstance(s, int) and s > 0
                    for s in steps]), "事件时钟步长不是正整数"
        self._steps = steps
        if offset >= 0:
            self._offset = offset
        else:
            self._offset = offset % -sum(self._steps)

    def prelude(self) -> Sequence[int]:
        if self._offset >= 0:
            return []
        steps = []
        t = self._offset
        for s in self._steps:
            t += s
            if t > 0:
                steps.append(t)
                t = 0
        assert steps
        return steps

    def ts(self, t: int) -> int:
        t += 1
        if self._offset >= 0:
            s = self._offset
        else:
            p = self.prelude()
            if t <= len(p):
                return sum(p[:t])
            s = sum(p)
            t -= len(p)
        return s + t // len(self._steps) * sum(self._steps) + sum(
            self._steps[:t % len(self._steps)])
