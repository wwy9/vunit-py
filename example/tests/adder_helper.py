import os.path
from vunit_py import Test, SignalHelper, CycleHelper

TESTS = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.dirname(TESTS)

t1 = Test("adder",
          "signal_test",
          os.path.join(TESTS, "__autogen__"),
          in_ports=["clk", "a", "b"],
          out_ports=[("sum", 2)])
sh = SignalHelper(t1)
sh.input(1, {"a": 0, "b": 0}).input(11, {"b": 1})
sh.output(6, {"sum": 0}).output(16, {"sum": 1})
sh.input(21, {"a": 1, "b": 0}).input(31, {"b": 1})
sh.output(26, {"sum": 1}).output(36, {"sum": 2})
sh.attach()
t1.addEventClock("ec_clk", 5)
t1["clk"]**"ec_clk" // 0 << [1, 0] * 10

t2 = Test("adder",
          "cycle_test",
          os.path.join(TESTS, "__autogen__"),
          in_ports=["clk", "a", "b"],
          out_ports=[("sum", 2)])
ch = CycleHelper(t2)
ch.add("a", 10, 0, [1]).add("b", 20, 0, [3, 7]).add("sum", 20, 0, [6, 16])
ch.input("a", 0, [0]).input("a", 3, [1]).input("a", 5, [0])
ch.input("b", 0, [0, 1]).input("b", 2, [1, 0])
ch.output("sum", 0, [0, 1]).output("sum", 1, [1, 2]).output("sum", 2, [2, 0])
ch.fillOutput("sum", 2)
ch.attach()
t2.addEventClock("ec_clk", 5)
t2["clk"]**"ec_clk" // 0 << [1, 0] * 10

Test.run([t1, t2], dependencies=[os.path.join(EXAMPLE, "adder.sv")])
