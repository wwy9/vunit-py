module adder
(
    input clk,
    input a,
    input b,
    output reg[1:0] sum,
    input rst
);

always @(posedge rst)
begin
    sum <= 0;
end

always @(posedge clk)
begin
    sum <= a+b;
end

endmodule