// AEE SIM-002: UART Receiver Testbench
// SPEC-002 → RTL-002 → SIM-002

`timescale 1ns / 1ps

module uart_rx_tb;

    parameter CLK_PERIOD = 20;
    parameter BAUD_DIV = 434;
    parameter BIT_PERIOD = BAUD_DIV * CLK_PERIOD;

    // DUT signals
    reg clk;
    reg rst_n;
    reg [15:0] baud_div;
    wire [7:0] rx_data;
    wire rx_valid;
    reg rx_ready;
    reg rx;
    wire parity_error;
    wire frame_error;

    // DUT
    uart_rx dut (
        .clk(clk),
        .rst_n(rst_n),
        .baud_div(baud_div),
        .rx_data(rx_data),
        .rx_valid(rx_valid),
        .rx_ready(rx_ready),
        .rx(rx),
        .parity_error(parity_error),
        .frame_error(frame_error)
    );

    // Clock
    initial clk = 0;
    always #(CLK_PERIOD/2) clk = ~clk;

    // Test variables
    integer error_count;
    integer i;
    reg [7:0] test_byte;
    reg [9:0] tx_frame;

    // Task: send a byte over the RX line
    task send_byte;
        input [7:0] data_byte;
        integer i;
        begin
            // Send start bit
            rx = 1'b0;
            #(BIT_PERIOD);

            // Send 8 data bits (LSB first)
            for (i = 0; i < 8; i = i + 1) begin
                rx = data_byte[i];
                #(BIT_PERIOD);
            end

            // Send stop bit
            rx = 1'b1;
            #(BIT_PERIOD);
        end
    endtask

    // Main test
    initial begin
        // Initialize
        rst_n = 0;
        rx = 1;
        rx_ready = 1;
        baud_div = BAUD_DIV;
        error_count = 0;

        // Reset
        #(CLK_PERIOD * 10);
        rst_n = 1;
        #(CLK_PERIOD * 10);

        $display("=== UART RX Testbench ===");
        $display("Clock: 50 MHz, Baud: 115200, Divider: %0d", BAUD_DIV);

        // Test 1: Receive 0x55
        $display("\n--- Test 1: 0x55 ---");
        send_byte(8'h55);
        @(posedge rx_valid);
        $display("Received: 0x%02X", rx_data);
        if (rx_data !== 8'h55) begin
            $display("ERROR: expected 0x55, got 0x%02X", rx_data);
            error_count = error_count + 1;
        end

        // Test 2: Receive 0x00
        $display("\n--- Test 2: 0x00 ---");
        send_byte(8'h00);
        @(posedge rx_valid);
        $display("Received: 0x%02X", rx_data);
        if (rx_data !== 8'h00) begin
            $display("ERROR: expected 0x00, got 0x%02X", rx_data);
            error_count = error_count + 1;
        end

        // Test 3: Receive 0xFF
        $display("\n--- Test 3: 0xFF ---");
        send_byte(8'hFF);
        @(posedge rx_valid);
        $display("Received: 0x%02X", rx_data);
        if (rx_data !== 8'hFF) begin
            $display("ERROR: expected 0xFF, got 0x%02X", rx_data);
            error_count = error_count + 1;
        end

        // Test 4: Receive 0xA5
        $display("\n--- Test 4: 0xA5 ---");
        send_byte(8'hA5);
        @(posedge rx_valid);
        $display("Received: 0x%02X", rx_data);
        if (rx_data !== 8'hA5) begin
            $display("ERROR: expected 0xA5, got 0x%02X", rx_data);
            error_count = error_count + 1;
        end

        // Summary
        #(CLK_PERIOD * 100);
        $display("\n=== Test Summary ===");
        if (error_count == 0) begin
            $display("PASS: All tests passed");
        end else begin
            $display("FAIL: %0d errors detected", error_count);
        end

        $finish;
    end

    // Timeout
    initial begin
        #(CLK_PERIOD * 100000);
        $display("ERROR: Simulation timeout");
        $finish;
    end

endmodule
