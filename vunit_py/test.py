from typing import Dict, List, Tuple, Union
import os.path

from vunit.verilog import VUnit

from .event_clock import EventClock
from .value import Logic, Value
from .port import Port, PortType, EventClockContainerProtocol

PortDef = Union[str, Tuple[str, int]]


class Test(EventClockContainerProtocol):
    moduleName: str
    testName: str
    __path: str
    __clocks: Dict[str, EventClock]
    _inPorts: Dict[str, Port]
    _outPorts: Dict[str, Port]
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
        self._inPorts = {}
        self._outPorts = {}
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
            assert port not in self._inPorts, "端口 {} 已定义".format(port)
            self._inPorts[port] = Port(PortType.IN, width, self)

        for pd in out_ports:
            port, width = extract(pd)
            assert port not in self._inPorts, "端口 {} 已定义".format(port)
            assert port not in self._outPorts, "端口 {} 已定义".format(port)
            self._outPorts[port] = Port(PortType.OUT, width, self)

    def __getitem__(self, port: str) -> Port:
        if port in self._inPorts:
            return self._inPorts[port]
        assert port in self._outPorts, "端口 {} 未定义".format(port)
        return self._outPorts[port]

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
        for name, port in self._inPorts.items():
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

        for name, port in self._outPorts.items():
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
                        port = self._inPorts[p]
                        if t < len(port._input):
                            f.write(str(port._input[t]))
                        else:
                            f.write(str(port._input[-1]))
                        f.write("_")
                    f.write("\n")
        return True

    # 此函数不能有类型，否则 VUnit 不工作
    def check(self):
        def printDiff(value: Value, expected: Value) -> None:
            print("{p} @{ts} ({t}x): expected".format(
                p=p, ts=self.__clocks[clk].ts(t), t=t))
            try:
                print(">> {w}'d{v} ({w}'h{v:x}) ({w}'b{s})".format(
                    w=len(expected), v=int(expected), s=str(expected)))
            except Exception:
                print(">> {w}'b{s}".format(w=len(expected), s=str(expected)))
            print("got")
            try:
                print(">> {w}'d{v} ({w}'h{v:x}) ({w}'b{s})".format(
                    w=len(value), v=int(value), s=str(value)))
            except Exception:
                print(">> {w}'b{s}".format(w=len(value), s=str(value)))

        def checkEq(p: str, value: Value, expected: Value) -> bool:
            if len(value) != len(expected):
                printDiff(value, expected)
                return False
            for i, v in enumerate(expected):
                if v == Logic.X:
                    continue
                if value[i] != v:
                    printDiff(value, expected)
                    return False
            return True

        ret = True
        for clk, ports in self.__outputs.items():
            values = []
            width = sum([self._outPorts[p].width for p in ports])
            with open(self.prefix() + "_" + clk + ".out", "r") as f:
                lines = f.readlines()
                values = [
                    Value.fromStr(l.strip(), width) for l in lines
                    if l[0] != "/"
                ]
            assert len(values) >= self.__outLens[clk], "文件长度不足"
            for t in range(self.__outLens[clk]):
                start = 0
                for p in ports:
                    port = self._outPorts[p]
                    if t < len(port._output):
                        if not checkEq(p, values[t][start:start + port.width],
                                       port._output[t]):
                            ret = False
                    start += port.width
        return ret

    def write(self) -> None:
        reg_define = ""
        reg_init = ""
        clk_gen = ""
        port_assign = ""
        param_assign = ""
        data_write = ""
        maxTs = 0

        for p in self.__statics:
            port = self._inPorts[p]
            input_name = "AUTOGEN_static_{}".format(p)
            reg_define += "wire[0:{}] {} = {}'b{};\n".format(
                port.width - 1, input_name, port.width, str(port._initValue))
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
                initValueStr = ""
                for p in self.__inputs[clk]:
                    port = self._inPorts[p]
                    port_assign += "    .{}({}[{}:{}]),\n".format(
                        p, input_name, start, start + port.width - 1)
                    if hasattr(port, "_initValue") and port._initValue:
                        initValueStr += str(port._initValue)
                    else:
                        initValueStr += "x" * port.width
                    start += port.width

                reg_define += "reg[0:{}] {};\n".format(start - 1, input_name)
                reg_define += "reg[0:{}] {}[0:{}];\n".format(
                    start - 1, input_data_name, duration - 1)
                reg_init += "  {} = {}'b{};\n".format(input_name, start,
                                                      initValueStr)
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
                    port = self._outPorts[p]
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
