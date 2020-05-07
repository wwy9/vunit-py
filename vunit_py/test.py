from typing import Dict, List, Tuple, Union
from enum import Enum
import os.path

from vunit.verilog import VUnit


class EventClock(object):
    _steps: List[int]
    _offset: int

    def __init__(self, steps: List[int], offset: int):
        assert all([isinstance(s, int) and s > 0
                    for s in steps]), "事件时钟步长不是正整数"
        self._steps = steps
        if offset >= 0:
            self._offset = offset
        else:
            self._offset = offset % -sum(self._steps)

    def prelude(self) -> List[int]:
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


class PortType(Enum):
    IN = 1
    OUT = 2


class Value(Enum):
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

    @staticmethod
    def valuesToString(value: List["Value"]) -> str:
        return "".join([str(v) for v in value])

    @staticmethod
    def valuesToInteger(value: List["Value"]) -> int:
        assert all([v == Value.LO or v == Value.HI
                    for v in value]), "包含 x 或 z 的值无法转换为整数"
        res = 0
        for v in value:
            res <<= 1
            res |= 1 if v == Value.HI else 0
        return res

    @staticmethod
    def fromChar(c: str) -> "Value":
        if c == "0":
            return Value.LO
        elif c == "1":
            return Value.HI
        elif c == "x" or c == "X":
            return Value.X
        elif c == "z" or c == "Z":
            return Value.Z
        assert False, "值包含非法字符：{}".format(c)

    @staticmethod
    def valuesFromInt(v: int, width: int) -> List["Value"]:
        return [
            Value.HI if (v >> (width - 1 - i)) & 1 else Value.LO
            for i in range(width)
        ]

    @staticmethod
    def valuesFromStr(s: str) -> List["Value"]:
        return [v for c in s for v in Value.valuesFromInt(ord(c), 8)]

    @staticmethod
    def valuesFromAny(input: Union[int, str], width: int) -> List["Value"]:
        if isinstance(input, str):
            assert len(input) == width, "值的宽度不匹配：{} != {}".format(
                len(input), width)
            return [Value.fromChar(c) for c in input]
        assert input >= 0 and input < (
            1 << width), "不支持负数值" if input < 0 else "值宽度太大：{} > 2^{}".format(
                input, width)
        return Value.valuesFromInt(input, width)

    @staticmethod
    def hex2bin(s: str) -> str:
        return Value.valuesToString(Value.valuesFromStr(s))


SignalDef = Union[List[Union[int, str]], Dict[int, Union[int, str]], str]


class Port(object):
    portType: PortType
    width: int
    _clk: str
    _initValue: List[Value]
    _input: List[List[Value]]
    _output: List[List[Value]]
    __parent: "Test"

    def __init__(self, portType: PortType, width: int, parent: "Test"):
        assert width > 0, "端口宽度不为正：{}".format(width)
        self.portType = portType
        self.width = width
        self.__parent = parent
        if portType == PortType.IN:
            self._input = []
        elif portType == PortType.OUT:
            self._output = []

    def __pow__(self, clk: str) -> "Port":
        assert self.__parent.hasClock(clk), "事件时钟不存在：{}".format(clk)
        self._clk = clk
        return self

    def normalize(self, input: SignalDef) -> List[List[Value]]:
        def reshape(values: List[Value]) -> List[List[Value]]:
            return [
                values[i * self.width:(i + 1) * self.width]
                for i in range(len(values) // self.width)
            ]

        if isinstance(input, str):
            assert (self.width & (self.width - 1)
                    ) == 0, "使用字符串形式表达信号序列时，端口宽度不为 2 的幂次：{}".format(self.width)
            if self.width > 8:
                assert len(input) % (
                    self.width /
                    8) == 0, "使用字符串形式表达信号序列时，序列长度不是端口宽度的倍数：{} | {}".format(
                        len(input) * 8, self.width)
            return reshape(Value.valuesFromStr(input))
        elif isinstance(input, dict):
            vs = sorted([(t, Value.valuesFromAny(x, self.width))
                         for t, x in input.items()],
                        key=lambda x: x[0])
            if self.portType == PortType.OUT:
                assert vs[0][0] >= len(
                    self._output
                ), "使用字典形式表达信号序列时，指定的时间小于当前序列长度：{} < {}".format(
                    vs[0][0], len(self._output))
                value = [[Value.X] * self.width
                         ] * (vs[-1][0] + 1 - len(self._output))
                for t, v in vs:
                    value[t - len(self._output)] = v
            else:
                assert vs[0][0] >= len(
                    self._input), "使用字典形式表达信号序列时，指定的时间小于当前序列长度：{} < {}".format(
                        vs[0][0], len(self._output))
                lastT = len(self._input) - 1
                lastV = self._input[
                    -1] if self._input else self._initValue if hasattr(
                        self, "_initValue"
                    ) and self._initValue else [Value.X] * self.width
                value = []
                for t, v in vs:
                    value += [lastV] * (t - lastT - 1)
                    value.append(v)
                    lastT = t
                    lastV = v
            return value
        else:
            return [Value.valuesFromAny(x, self.width) for x in input]

    def __floordiv__(self, input: Union[int, str]) -> "Port":
        assert self.portType == PortType.IN, "输出端口不可定义初始值"
        assert not self._input, "定义输入序列后，不可定义初始值"
        self._initValue = Value.valuesFromAny(input, self.width)
        return self

    def __lshift__(self, input: SignalDef) -> "Port":
        assert self.portType == PortType.IN, "输出端口不可定义输入（输出定义方式为 >>）"
        self._input += self.normalize(input)
        return self

    def __rshift__(self, output: SignalDef) -> "Port":
        assert self.portType == PortType.OUT, "输入端口不可定义输出（输入定义方式为 <<）"
        self._output += self.normalize(output)
        return self


PortDef = Union[str, Tuple[str, int]]


class Test(object):
    moduleName: str
    testName: str
    __path: str
    __clocks: Dict[str, EventClock]
    __inPorts: Dict[str, Port]
    __outPorts: Dict[str, Port]
    __parameters: Dict[str, str]
    # [port]
    __statics: List[str]
    # {clk: [port]}
    __inputs: Dict[str, List[str]]
    # {clk: [port]}
    __outputs: Dict[str, List[str]]
    # {clk : max_t}
    __inLens: Dict[str, int]
    # {clk : max_t}
    __outLens: Dict[str, int]

    def __init__(
        self,
        module_name: str,
        test_name: str,
        output_path: str,
        in_ports: List[PortDef] = [],
        out_ports: List[PortDef] = [],
        parameters: Dict[str, Union[int, str]] = {},
    ):
        self.moduleName = module_name
        self.testName = test_name
        self.__path = os.path.abspath(output_path)
        self.__clocks = {}
        self.__inPorts = {}
        self.__outPorts = {}
        self.__parameters = {k: str(v) for k, v in parameters.items()}
        self.__statics = []
        self.__inputs = {}
        self.__outputs = {}
        self.__inLens = {}
        self.__outLens = {}

        def extract(pd: PortDef) -> Tuple[str, int]:
            if isinstance(pd, str):
                return (pd, 1)
            return pd

        for pd in in_ports:
            port, width = extract(pd)
            assert port not in self.__inPorts, "端口 {} 已定义".format(port)
            self.__inPorts[port] = Port(PortType.IN, width, self)

        for pd in out_ports:
            port, width = extract(pd)
            assert port not in self.__inPorts, "端口 {} 已定义".format(port)
            assert port not in self.__outPorts, "端口 {} 已定义".format(port)
            self.__outPorts[port] = Port(PortType.OUT, width, self)

    def __getitem__(self, port: str) -> Port:
        if port in self.__inPorts:
            return self.__inPorts[port]
        assert port in self.__outPorts, "端口 {} 未定义".format(port)
        return self.__outPorts[port]

    def addEventClock(self,
                      clk: str,
                      steps: Union[int, List[int]],
                      offset: int = 0) -> None:
        assert clk not in self.__clocks, "事件时钟 {} 已定义".format(clk)
        if isinstance(steps, list):
            self.__clocks[clk] = EventClock(steps, offset)
        else:
            self.__clocks[clk] = EventClock([steps], offset)

    def hasClock(self, clk: str) -> bool:
        return clk in self.__clocks

    def gen(self) -> None:
        for name, port in self.__inPorts.items():
            if hasattr(port, "_input") and port._input:
                assert hasattr(
                    port, "_clk"), "端口 {} 定义了输入序列，但是未依附于任何事件时钟".format(name)
                assert port._clk in self.__clocks, \
                    "端口 {} 所依附的事件时钟不存在：{}".format(name, port._clk)
                if port._clk not in self.__inputs:
                    self.__inputs[port._clk] = []
                self.__inputs[port._clk].append(name)
                self.__inLens[port._clk] = max(self.__inLens.get(port._clk, 0),
                                               len(port._input))
            elif hasattr(port, "_initValue") and port._initValue:
                self.__statics.append(name)

        for name, port in self.__outPorts.items():
            if hasattr(port, "_output") and port._output:
                assert hasattr(
                    port, "_clk"), "端口 {} 定义了输出序列，但是未依附于任何事件时钟".format(name)
                assert port._clk in self.__clocks, \
                    "端口 {} 所依附的事件时钟不存在：{}".format(name, port._clk)
                if port._clk not in self.__outputs:
                    self.__outputs[port._clk] = []
                self.__outputs[port._clk].append(name)
                self.__outLens[port._clk] = max(
                    self.__outLens.get(port._clk, 0), len(port._output))

    def prefix(self, escape: bool = False) -> str:
        p = os.path.join(self.__path,
                         "tb_" + self.moduleName + "_" + self.testName)
        if escape:
            return p.replace("\\", "\\\\")
        return p

    def dump(self) -> bool:
        for clk, ports in self.__inputs.items():
            with open(self.prefix() + "_" + clk + ".in", "w") as f:
                for t in range(self.__inLens[clk]):
                    for p in ports:
                        port = self.__inPorts[p]
                        if t < len(port._input):
                            f.write(Value.valuesToString(port._input[t]))
                        else:
                            f.write(Value.valuesToString(port._input[-1]))
                        f.write("_")
                    f.write("\n")
        return True

    def check(self):
        def eq(value: List[Value], expected: List[Value]) -> bool:
            for i, v in enumerate(expected):
                if v == Value.X:
                    continue
                if value[i] != v:
                    print("{} @{} ({}x): expected".format(
                        p,
                        self.__clocks[clk].ts(t),
                        t,
                    ))
                    try:
                        print(">> {}'d{} ({}'h{:x}) ({})".format(
                            len(expected), Value.valuesToInteger(expected),
                            len(expected), Value.valuesToInteger(expected),
                            Value.valuesToString(expected)))
                    except Exception:
                        print(">> {}".format(Value.valuesToString(expected)))
                    print("got")
                    try:
                        print(">> {}'d{} ({}'h{:x}) ({})".format(
                            len(value), Value.valuesToInteger(value),
                            len(value), Value.valuesToInteger(value),
                            Value.valuesToString(value)))
                    except Exception:
                        print(">> {}".format(Value.valuesToString(value)))
                    return False
            return True

        for clk, ports in self.__outputs.items():
            values = []
            with open(self.prefix() + "_" + clk + ".out", "r") as f:
                lines = f.readlines()
                values = [[Value.fromChar(c) for c in l.strip()] for l in lines
                          if l[0] != "/"]
            assert len(values) >= self.__outLens[clk], "文件有多余内容"
            for t in range(self.__outLens[clk]):
                start = 0
                for p in ports:
                    port = self.__outPorts[p]
                    if t < len(port._output):
                        if not eq(values[t][start:start + port.width],
                                  port._output[t]):
                            return False
                    start += port.width
        return True

    def write(self) -> None:
        reg_define = ""
        reg_init = ""
        clk_gen = ""
        port_assign = ""
        param_assign = ""
        data_write = ""
        maxTs = 0

        for p in self.__statics:
            port = self.__inPorts[p]
            input_name = "AUTOGEN_static_{}".format(p)
            reg_define += "wire[0:{}] {} = {}'b{};\n".format(
                port.width - 1, input_name, port.width,
                Value.valuesToString(port._initValue))
            port_assign += "    .{}({}[{}:{}]),\n".format(
                p, input_name, 0, port.width - 1)

        for clk, c in self.__clocks.items():
            cnt_name = "AUTOGEN_{}_cnt".format(clk)
            input_name = "AUTOGEN_{}_input".format(clk)
            input_data_name = "AUTOGEN_{}_input_data".format(clk)
            output_name = "AUTOGEN_{}_output".format(clk)
            output_data_name = "AUTOGEN_{}_output_data".format(clk)

            step_action = ""
            clk_action = ""

            reg_define += "integer {};\n".format(cnt_name)

            if clk in self.__inputs:
                assert clk in self.__inLens
                duration = self.__inLens[clk]
                start = 0
                initValue = []
                for p in self.__inputs[clk]:
                    port = self.__inPorts[p]
                    port_assign += "    .{}({}[{}:{}]),\n".format(
                        p, input_name, start, start + port.width - 1)
                    if hasattr(port, "_initValue") and port._initValue:
                        initValue += port._initValue
                    else:
                        initValue += [Value.X] * port.width
                    start += port.width

                reg_define += "reg[0:{}] {};\n".format(start - 1, input_name)
                reg_define += "reg[0:{}] {}[0:{}];\n".format(
                    start - 1, input_data_name, duration - 1)
                reg_init += "  {} = {}'b{};\n".format(
                    input_name, start, Value.valuesToString(initValue))
                reg_init += "  $readmemb(\"{}\", {});\n".format(
                    self.prefix(True) + "_" + clk + ".in", input_data_name)
                step_action += "        if ({} < {})\n".format(
                    cnt_name, duration)
                step_action += "        begin\n"
                step_action += "          {} = {}[{}];\n".format(
                    input_name, input_data_name, cnt_name)
                step_action += "        end\n"

            if clk in self.__outputs:
                assert clk in self.__outLens
                duration = self.__outLens[clk]
                start = 0
                for p in self.__outputs[clk]:
                    port = self.__outPorts[p]
                    port_assign += "    .{}({}[{}:{}]),\n".format(
                        p, output_name, start, start + port.width - 1)
                    start += port.width

                reg_define += "wire[0:{}] {};\n".format(start - 1, output_name)
                reg_define += "reg[0:{}] {}[0:{}];\n".format(
                    start - 1, output_data_name, duration - 1)
                step_action += "        if ({} < {})\n".format(
                    cnt_name, duration)
                step_action += "        begin\n"
                step_action += "          {}[{}] = {};\n".format(
                    output_data_name, cnt_name, output_name)
                step_action += "        end\n"
                maxTs = max(maxTs, c.ts(duration))

            assert step_action, "没有任何端口依附于事件时钟 {}，请检查代码".format(clk)
            step_action += "        {0} = {0} + 1;\n".format(cnt_name)

            d = duration
            if c._offset < 0:
                clk_action += "      {} = 0;\n".format(cnt_name)
                prelude = c.prelude()
                for s in prelude[:d]:
                    clk_action += "      #{}\n{}".format(s, step_action)
                d = max(0, d - len(prelude))
            elif c._offset == 0:
                clk_action += "      {} = 0;\n".format(cnt_name)
            else:
                clk_action += "      #{} {} = 0;\n".format(c._offset, cnt_name)
            if d > len(c._steps):
                clk_action += "      repeat ({})\n".format(d // len(c._steps))
                clk_action += "      begin\n"
                for s in c._steps:
                    clk_action += "      #{}\n{}".format(s, step_action)
                clk_action += "      end\n"
                d %= len(c._steps)
            for s in c._steps[:d]:
                clk_action += "      #{}\n{}".format(s, step_action)
            clk_gen += "    begin\n{}    end\n".format(clk_action)

        for clk, ports in self.__outputs.items():
            data_name = "AUTOGEN_{}_output_data".format(clk)
            data_write += "    #{} $writememb(\"{}\", {});\n".format(
                maxTs + 1,
                self.prefix(True) + "_" + clk + ".out", data_name)

        for k, v in self.__parameters.items():
            param_assign += "    .{}({}),\n".format(k, v)

        sv = """`timescale 1ns/100ps
`include "vunit_defines.svh"

module tb_{module}_{test};

{reg_define}

initial
begin
{reg_init}
  fork
{clk_gen}
  join
end

{module}
  #(
{param_assign}
  )
  uut
  (
{port_assign}
  );

`TEST_SUITE
begin
  `TEST_CASE("{test}")
  begin
{data_write}
  end
end

endmodule
""".format(module=self.moduleName,
           reg_define=reg_define[:-1],
           reg_init=reg_init[:-1],
           clk_gen=clk_gen[:-1],
           param_assign=param_assign[:-2],
           port_assign=port_assign[:-2],
           test=self.testName,
           data_write=data_write[:-1])

        with open(self.prefix() + ".sv", "w") as f:
            f.write(sv)

    @staticmethod
    def run(tests: List["Test"],
            dependencies: List[Union[str, Tuple[str, Dict[str, str]]]] = [],
            include_dirs: List[str] = [],
            external_libraries: Dict[str, str] = {}) -> None:
        s = set()
        for t in tests:
            assert (t.moduleName, t.testName) not in s, "模块 {} 已有测试 {}".format(
                t.moduleName, t.testName)
            s.add((t.moduleName, t.testName))
        vu = VUnit.from_argv()
        for name, path in external_libraries.items():
            vu.add_external_library(name, path)
        dep = vu.add_library("dep")
        for d in dependencies:
            if isinstance(d, str):
                dep.add_source_file(d,
                                    include_dirs=include_dirs,
                                    no_parse=True)
            else:
                dep.add_source_file(d[0],
                                    include_dirs=include_dirs,
                                    no_parse=True,
                                    defines=d[1])
        lib = vu.add_library("lib")
        for t in tests:
            t.gen()
            t.write()
            t.dump()
            lib.add_source_file(t.prefix() + ".sv", include_dirs=include_dirs)
        for t in tests:
            lib.test_bench("tb_" + t.moduleName + "_" +
                           t.testName).set_post_check(t.check)
        vu.main()
