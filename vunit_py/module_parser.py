from typing import List, Sequence
from pathlib import Path
import re

from .test import PortDef

MODULE_REGEX = r"module\s+(\w+)\s*\(([^)]*)\)"
MODULE_DEF = re.compile(MODULE_REGEX, re.A | re.I)
PORT_REGEX = r"\s*(input|output)((?:\s+(?:unsigned|signed|reg|wire))*)(?:\[\s*(\d+)(?:\s*:\s*(\d+))?\s*\])?\s*(\w+)\s*"
PORT_DEF = re.compile(PORT_REGEX, re.A | re.I)


class ModuleParser:
    __inputs: List[PortDef]
    __outputs: List[PortDef]

    def __init__(self, file: Path, name: str) -> None:
        self.__inputs = []
        self.__outputs = []
        with open(file, "r") as f:
            s = f.read()
            pos: int = 0
            while True:
                m = MODULE_DEF.search(s, pos)
                if not m:
                    raise RuntimeError("cannot find module " + name)
                pos = m.endpos
                if m.group(1) != name:
                    continue
                for p in m.group(2).split(','):
                    pm = PORT_DEF.fullmatch(p)
                    if not pm:
                        raise RuntimeError("cannot parse port def: " + p)
                    w: int = 1
                    if pm.group(3) is not None and pm.group(4) is not None:
                        w = abs(int(pm.group(3)) - int(pm.group(4))) + 1
                    if "signed" in re.split(r"\s+", pm.group(2)):
                        w = -w
                    if pm.group(1) == "input":
                        self.__inputs.append((pm.group(5), w))
                    else:
                        self.__outputs.append((pm.group(5), w))
                break

    @property
    def inputs(self) -> Sequence[PortDef]:
        return self.__inputs

    @property
    def outputs(self) -> Sequence[PortDef]:
        return self.__outputs
