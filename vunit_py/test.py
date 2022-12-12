from typing import Dict, List, Mapping, Sequence, Tuple, Union
from pathlib import Path

from vunit.verilog import VUnit

from .event_clock import EventClock
from .value import Logic, Value
from .port import Port, PortType, EventClockContainerProtocol

PortDef = Union[str, Tuple[str, int]]


class Test(EventClockContainerProtocol):
    """
    测试单元
    """
    __moduleName: str
    __testName: str
    __path: Path
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
    __reportAllErrors: bool

    def __init__(
        self,
        module_name: str,
        test_name: str,
        output_path: Path,
        in_ports: Sequence[PortDef] = [],
        out_ports: Sequence[PortDef] = [],
        parameters: Mapping[str, Union[int, str]] = {},
        report_all_errors: bool = False,
    ):
        """
        module_name: 需要测试的 verilog 模块名
        test_name: 测试单元名
        output_path: 生成的测试文件所在文件夹
        in_ports: 输入端口定义
        out_ports: 输出端口定义
        parameters: 模块参数定义
        report_all_errors: 是否报告所有不符合预期的输出, 若否则仅报告最早的输出
        """
        self.__moduleName = module_name
        self.__testName = test_name
        self.__path = output_path.absolute()
        self.__clocks = {}
        self.__inPorts = {}
        self.__outPorts = {}
        self.__parameters = {k: str(v) for k, v in parameters.items()}
        self.__statics = []
        self.__inputs = {}
        self.__outputs = {}
        self.__inLens = {}
        self.__outLens = {}
        self.__reportAllErrors = report_all_errors

        def extract(pd: PortDef) -> Tuple[str, int]:
            if isinstance(pd, str):
                return (pd, 1)
            return pd

        for pd in in_ports:
            port, width = extract(pd)
            assert port not in self.__inPorts, "端口 {} 已定义".format(port)
            if width >= 0:
                assert width > 0, "端口 {} 宽度为 0".format(port)
                self.__inPorts[port] = Port(PortType.IN, width, False, self)
            else:
                assert width < -1, "端口 {} 宽度为 1，无法定义有符号整数".format(port)
                self.__inPorts[port] = Port(PortType.IN, -width, True, self)

        for pd in out_ports:
            port, width = extract(pd)
            assert port not in self.__inPorts, "端口 {} 已定义".format(port)
            assert port not in self.__outPorts, "端口 {} 已定义".format(port)
            if width >= 0:
                assert width > 0, "端口 {} 宽度为 0".format(port)
                self.__outPorts[port] = Port(PortType.OUT, width, False, self)
            else:
                assert width < -1, "端口 {} 宽度为 1，无法定义有符号整数".format(port)
                self.__outPorts[port] = Port(PortType.OUT, -width, True, self)

    def __getitem__(self, port: str) -> Port:
        """
        取得输入/输出端口
        """
        if port in self.inPorts:
            return self.inPorts[port]
        assert port in self.outPorts, "端口 {} 未定义".format(port)
        return self.outPorts[port]

    @property
    def inPorts(self) -> Mapping[str, Port]:
        """
        输入端口
        """
        return self.__inPorts

    @property
    def outPorts(self) -> Mapping[str, Port]:
        """
        输出端口
        """
        return self.__outPorts

    def addEventClock(self,
                      clk: str,
                      steps: Union[int, Sequence[int]],
                      offset: int = 0) -> None:
        """
        添加事件时钟
        """
        assert clk not in self.__clocks, "事件时钟 {} 已定义".format(clk)
        if isinstance(steps, int):
            self.__clocks[clk] = EventClock([steps], offset)
        else:
            self.__clocks[clk] = EventClock(steps, offset)

    def hasClock(self, clk: str) -> bool:
        return clk in self.__clocks

    def __gen(self) -> None:
        """
        生成输入/输出序列
        """
        for name, port in self.inPorts.items():
            if port.input:
                msg = "端口 {} 定义了输入序列，但是未依附于任何事件时钟".format(name)
                assert port.clk, msg
                msg = "端口 {} 所依附的事件时钟不存在：{}".format(name, port.clk)
                assert port.clk in self.__clocks, msg
                if port.clk not in self.__inputs:
                    self.__inputs[port.clk] = []
                self.__inputs[port.clk].append(name)
                self.__inLens[port.clk] = max(self.__inLens.get(port.clk, 0),
                                              len(port.input))
            elif port.initValue is not None:
                self.__statics.append(name)

        for name, port in self.outPorts.items():
            if port.output:
                msg = "端口 {} 定义了输出序列，但是未依附于任何事件时钟".format(name)
                assert port.clk, msg
                msg = "端口 {} 所依附的事件时钟不存在：{}".format(name, port.clk)
                assert port.clk in self.__clocks, msg
                if port.clk not in self.__outputs:
                    self.__outputs[port.clk] = []
                self.__outputs[port.clk].append(name)
                self.__outLens[port.clk] = max(self.__outLens.get(port.clk, 0),
                                               len(port.output))

    def __write(self) -> None:
        """
        生成测试文件
        """
        reg_define = ""
        reg_init = ""
        clk_gen = ""
        port_assign = ""
        param_assign = ""
        data_write = ""
        maxTs = 0

        for p in self.__statics:
            port = self.inPorts[p]
            input_name = "AUTOGEN_static_{}".format(p)
            reg_define += "wire[0:{}] {} = {}'b{};\n".format(
                port.width - 1, input_name, port.width, port.initValue)
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
            duration = 0

            if clk in self.__inputs:
                assert clk in self.__inLens
                duration = self.__inLens[clk]
                start = 0
                initValueStr = ""
                for p in self.__inputs[clk]:
                    port = self.inPorts[p]
                    port_assign += "    .{}({}[{}:{}]),\n".format(
                        p, input_name, start, start + port.width - 1)
                    if port.initValue is not None:
                        initValueStr += str(port.initValue)
                    else:
                        initValueStr += "x" * port.width
                    start += port.width

                reg_define += "logic[0:{}] {};\n".format(start - 1, input_name)
                reg_define += "logic[0:{}] {}[0:{}];\n".format(
                    start - 1, input_data_name, duration - 1)
                reg_init += "  {} = {}'b{};\n".format(input_name, start,
                                                      initValueStr)
                reg_init += "  $readmemb(\"{}\", {});\n".format(
                    self.__genEscapedPath("_" + clk + ".in"), input_data_name)
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
                    port = self.outPorts[p]
                    port_assign += "    .{}({}[{}:{}]),\n".format(
                        p, output_name, start, start + port.width - 1)
                    start += port.width

                reg_define += "wire[0:{}] {};\n".format(start - 1, output_name)
                reg_define += "logic[0:{}] {}[0:{}];\n".format(
                    start - 1, output_data_name, duration - 1)
                step_action += "        if ({} < {})\n".format(
                    cnt_name, duration)
                step_action += "        begin\n"
                step_action += "          {}[{}] = {};\n".format(
                    output_data_name, cnt_name, output_name)
                step_action += "        end\n"
                maxTs = max(maxTs, c[duration])

            assert step_action, "没有任何端口依附于事件时钟 {}，请检查代码".format(clk)
            step_action += "        {0} = {0} + 1;\n".format(cnt_name)

            d = duration
            if c.offset < 0:
                clk_action += "      {} = 0;\n".format(cnt_name)
                for s in c.prelude[:d]:
                    clk_action += "      #{}\n{}".format(s, step_action)
                d = max(0, d - len(c.prelude))
            elif c.offset == 0:
                clk_action += "      {} = 0;\n".format(cnt_name)
            else:
                clk_action += "      #{} {} = 0;\n".format(c.offset, cnt_name)
            if d > len(c.steps):
                clk_action += "      repeat ({})\n".format(d // len(c.steps))
                clk_action += "      begin\n"
                for s in c.steps:
                    clk_action += "      #{}\n{}".format(s, step_action)
                clk_action += "      end\n"
                d %= len(c.steps)
            for s in c.steps[:d]:
                clk_action += "      #{}\n{}".format(s, step_action)
            clk_gen += "    begin\n{}    end\n".format(clk_action)

        for clk in self.__outputs:
            data_name = "AUTOGEN_{}_output_data".format(clk)
            data_write += "    $writememb(\"{}\", {});\n".format(
                self.__genEscapedPath("_" + clk + ".out"), data_name)

        for k, v in self.__parameters.items():
            param_assign += "    .{}({}),\n".format(k, v)

        sv = """`timescale 1ns/100ps
`include "vunit_defines.svh"

module tb_{module}_{test};

logic AUTOGEN_TEST_DONE;
{reg_define}

initial
begin
  AUTOGEN_TEST_DONE = 1'b0;
{reg_init}
  fork
  begin
    #{done_ts} AUTOGEN_TEST_DONE = 1'b1;
  end
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
    while(1) begin
      #1 if (AUTOGEN_TEST_DONE) begin
        break;
      end
    end
{data_write}
  end
end

endmodule
""".format(module=self.__moduleName,
           reg_define=reg_define[:-1],
           reg_init=reg_init[:-1],
           done_ts=maxTs + 1,
           clk_gen=clk_gen[:-1],
           param_assign=param_assign[:-2],
           port_assign=port_assign[:-2],
           test=self.__testName,
           data_write=data_write[:-1])

        with open(self.__genPath(".sv"), "w") as f:
            f.write(sv)

    def __dump(self) -> bool:
        """
        生成测试数据
        """
        for clk, ports in self.__inputs.items():
            with open(self.__genPath("_" + clk + ".in"), "w") as f:
                for t in range(self.__inLens[clk]):
                    for p in ports:
                        port = self.inPorts[p]
                        if t < len(port.input):
                            f.write(str(port.input[t]))
                        else:
                            f.write(str(port.input[-1]))
                        f.write("_")
                    f.write("\n")
        return True

    def __genPath(self, suffix: str) -> Path:
        """
        生成文件前缀
        """
        return self.__path / ("tb_" + self.__moduleName + "_" +
                              self.__testName + suffix)

    def __genEscapedPath(self, suffix: str) -> str:
        """
        生成文件前缀
        """
        return str(self.__genPath(suffix)).replace("\\", "\\\\")

    # 此函数不能有类型，否则 VUnit 不工作
    def __check(self):
        """
        读取并检查输出
        """

        def diffMsg(p: str, t: int, ts: int, value: Value,
                    expected: Value) -> str:
            msg = "{p} @{ts} ({t}x) 期望值：\n".format(p=p, ts=ts, t=t)
            try:
                msg += ">> {w}'d{v} ({w}'h{v:x}) ({w}'b{s})\n".format(
                    w=expected.width, v=int(expected), s=expected)
            except Exception:
                msg += ">> {w}'b{s}\n".format(w=expected.width, s=expected)
            msg += "实际值：\n"
            try:
                msg += ">> {w}'d{v} ({w}'h{v:x}) ({w}'b{s})\n".format(
                    w=value.width, v=int(value), s=value)
            except Exception:
                msg += ">> {w}'b{s}\n".format(w=value.width, s=value)
            return msg

        def checkEq(value: Value, expected: Value) -> bool:
            if value.width != expected.width:
                return False
            for i, v in enumerate(expected):
                if v == Logic.X:
                    continue
                if value[i] != v:
                    return False
            return True

        ret = True
        msgs = {}
        for clk, ports in self.__outputs.items():
            values = []
            width = sum([self.outPorts[p].width for p in ports])
            with open(self.__genPath("_" + clk + ".out"), "r") as f:
                lines = f.readlines()
                values = [
                    Value.fromStr(line.strip(), width, False) for line in lines
                    if line[0] != "/"
                ]
            assert len(values) >= self.__outLens[clk], "文件长度不足"
            for t in range(self.__outLens[clk]):
                start = 0
                for p in ports:
                    port = self.outPorts[p]
                    if t < len(port.output):
                        if not checkEq(values[t][start:start + port.width],
                                       port.output[t]):
                            ts = self.__clocks[clk][t]
                            if ts not in msgs:
                                msgs[ts] = []
                            msgs[ts].append(
                                diffMsg(p, t, ts,
                                        values[t][start:start + port.width],
                                        port.output[t]))
                            ret = False
                    start += port.width
        if self.__reportAllErrors:
            for t, ms in sorted(msgs.items(), key=lambda x: x[0]):
                for m in ms:
                    print(m)
        elif msgs:
            ts = sorted(msgs)[0]
            for m in msgs[ts]:
                print(m)
        return ret

    @staticmethod
    def run(
        tests: Sequence["Test"],
        dependencies: Sequence[Union[Path, Tuple[Path, Mapping[str,
                                                               str]]]] = [],
        auto_dependency: bool = False,
        include_dirs: Sequence[Path] = [],
        external_libraries: Mapping[str, Path] = {},
    ) -> None:
        s = set()
        for t in tests:
            msg = "模块 {} 已有测试 {}".format(t.__moduleName, t.__testName)
            assert (t.__moduleName, t.__testName) not in s, msg
            s.add((t.__moduleName, t.__testName))
        vu = VUnit.from_argv()
        for name, path in external_libraries.items():
            vu.add_external_library(name, path)
        dep = vu.add_library("dep")
        lastF = None
        for d in dependencies:
            if isinstance(d, Path):
                f = dep.add_source_file(d,
                                        include_dirs=include_dirs,
                                        no_parse=not auto_dependency)
            else:
                f = dep.add_source_file(d[0],
                                        include_dirs=include_dirs,
                                        no_parse=not auto_dependency,
                                        defines=d[1])
            if not auto_dependency:
                if lastF is not None:
                    f.add_dependency_on(lastF)
                lastF = f
        lib = vu.add_library("lib")
        for t in tests:
            t.__path.mkdir(parents=True, exist_ok=True)
            t.__gen()
            t.__write()
            t.__dump()
            lib.add_source_file(t.__genPath(".sv"), include_dirs=include_dirs)
        for t in tests:
            lib.test_bench("tb_" + t.__moduleName + "_" +
                           t.__testName).set_post_check(t.__check)
        vu.main()
