import sys
import os.path

TESTS = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.dirname(TESTS)
ROOT = os.path.dirname(EXAMPLE)

# 这是 hack，不要这么用，请把 test.py 放到正确的地方
sys.path = [ROOT] + sys.path
from test import Test, Value

###########
# 开始一个简单的测试用例
t1 = Test(
    "adder",
    "sum_test",
    os.path.join(TESTS, "__autogen__"),
    # 不用的端口可以不写
    in_ports=["clk", "a", "b"],
    out_ports=[("sum", 2)])
# 最简单的事件时钟，每个时刻都会发生事件
t1.addEventClock("ec_clk", 1)
# 最简单的时钟设置，注意次数不要太多，否则会生成一个巨大的寄存器数组
# 事件对应如下：
# 时间 #0 #1 #2 #3 #4 #5 #6
# 次数     0  1  2  3  4  5
# 信号  0  1  0  1  0  1  0
#      ^初始值
t1["clk"]**"ec_clk" // 0 << [1, 0] * 100
# 在 clk 下降沿的时候写入和读取数据
t1.addEventClock("ec", 2)
# 事件对应如下：
# 时间 #0 #1 #2 #3 #4 #5 #6
# 次数        0     1     2
# 信号  0     0     1     1
#      ^初始值
a = [0, 1, 1, 0]
t1["a"]**"ec" // 0 << a
# 事件对应如下：
# 时间 #0 #1 #2 #3 #4 #5 #6
# 次数        0     1     2
# 信号  X     1     1     0
#      ^初始值
b = [1, 1, 0, 0]
t1["b"]**"ec" << b
# 事件对应如下：
# 时间 #0 #1 #2 #3 #4 #5 #6
# 次数        0     1     2
# 信号        X     1     1
# 虽然时序需要自己操心，但是逻辑可以用 python 直接写出来
t1["sum"]**"ec" >> ["xx"] >> [ax + bx for ax, bx in zip(a, b)]
# 测试用例到此结束
###########

t2 = Test("adder",
          "rst_test",
          os.path.join(TESTS, "__autogen__"),
          in_ports=["clk", "a", "b", "rst"],
          out_ports=[("sum", 2)])
t2.addEventClock("ec_clk", 5)
t2["clk"]**"ec_clk" // 0 << [1, 0] * 100
# 精细控制 rst 时机
# 时间  #0  #5 #10 #15 #20 #25 #30 #35 #40
# clk   0   1   0   1   0   1   0   1   0
# rst                0 1             2 3
# 间隔        16       1       19      1
t2.addEventClock("ec_rst", [16, 1, 19, 1])
t2["rst"]**"ec_rst" // 0 << [1, 0] * 100
t2.addEventClock("ec", 10)
# 时间 #0  #5 #10 #15 #20 #25 #30 #35 #40 #45 #50
# clk  0   1   0   1   0   1   0   1   0   1   0
# rst               0 1             2 3
# 次数          0       1       2       3       4
#   a  0       0       1       1       0       1
#   b  X       1       1       0       1       1
# sum          X       0       2       0       1       2
# 信号序列可以混合各种表达方式
t2["a"]**"ec" // 0 << {1: 1, 3: 0} << [1]
# 端口设置可以拆开
t2["b"]**"ec"
t2["b"] << "\xdf"
# 可以把花式定义的输入信号变成数字
a = [Value.valuesToInteger(i) for i in t2["a"]._input]
b = [Value.valuesToInteger(i) for i in t2["b"]._input]
sum = [ax + bx for ax, bx in zip(a, b)]
sum[0] = sum[2] = 0
t2["sum"]**"ec" >> ["xx"] >> sum

Test.run([t1, t2], [EXAMPLE])
