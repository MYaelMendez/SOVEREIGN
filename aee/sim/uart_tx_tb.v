// AEE SIM-001: UART Transmitter Testbench
// SPEC-001 → RTL → SIM
// æ:// Agentic Electronic Engineering
// Author: Yæl Méndez
// Date: 2026-10-08

`timescale 1ns / 1ps

module uart_tx_tb;

    // Parameters
    parameter CLK_PERIOD = 20;  // 50 MHz
    parameter BAUD_DIV = 434;   // 115200 baud at 50 MHz
    parameter BIT_PERIOD = BAUD_DIV * CLK_PERIOD;

    // Signals
    reg clk;
    reg rst_n;
    reg [7:0] tx_data;
    reg tx_valid;
    wire tx_ready;
    wire tx;
    reg [15:0] baud_div;
    wire [4:0] fifo_count;
    wire fifo_full;
    wire fifo_empty;

    // DUT
    uart_tx #(
        .FIFO_DEPTH(16),
        .FIFO_AW(4)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .tx_data(tx_data),
        .tx_valid(tx_valid),
        .tx_ready(tx_ready),
        .tx(tx),
        .baud_div(baud_div),
        .fifo_count(fifo_count),
        .fifo_full(fifo_full),
        .fifo_empty(fifo_empty)
    );

    // Clock generation
    initial clk = 0;
    always #(CLK_PERIOD/2) clk = ~clk;

    // Test variables
    integer i;
    integer bit_idx;
    reg [7:0] test_byte;
    reg [9:0] received_frame;
    integer error_count;

    // Task: transmit a byte and capture the frame
    task transmit_byte;
        input [7:0] data_byte;
        begin
            // Wait for ready
            @(posedge clk);
            while (!tx_ready) @(posedge clk);

            // Write to FIFO
            tx_data = data_byte;
            tx_valid = 1;
            @(posedge clk);
            tx_valid = 0;

            // Wait for start bit (tx goes low)
            @(negedge tx);

            // Capture 10 bits (start + 8 data + stop)
            for (bit_idx = 0; bit_idx < 10; bit_idx = bit_idx + 1) begin
                #(BIT_PERIOD/2);  // Sample at center
                received_frame[bit_idx] = tx;
                #(BIT_PERIOD/2);
            end

            // Verify frame
            $display("Transmitted: 0x%02X, Received frame: %b", data_byte, received_frame);

            // Check start bit (should be 0)
            if (received_frame[0] !== 1'b0) begin
                $display("ERROR: Start bit is not 0");
                error_count = error_count + 1;
            end

            // Check data bits (LSB first)
            for (i = 0; i < 8; i = i + 1) begin
                if (received_frame[i+1] !== data_byte[i]) begin
                    $display("ERROR: Data bit %0d mismatch: expected %b, got %b",
                             i, data_byte[i], received_frame[i+1]);
                    error_count = error_count + 1;
                end
            end

            // Check stop bit (should be 1)
            if (received_frame[9] !== 1'b1) begin
                $display("ERROR: Stop bit is not 1");
                error_count = error_count + 1;
            end
        end
    endtask

    // Main test
    initial begin
        // Initialize
        rst_n = 0;
        tx_data = 0;
        tx_valid = 0;
        baud_div = BAUD_DIV;
        error_count = 0;
        received_frame = 0;

        // Reset
        #(CLK_PERIOD * 10);
        rst_n = 1;
        #(CLK_PERIOD * 10);

        $display("=== UART TX Testbench ===");
        $display("Clock: 50 MHz, Baud: 115200, Divider: %0d", BAUD_DIV);

        // Test 1: Transmit 0x55 (alternating pattern)
        $display("\n--- Test 1: 0x55 ---");
        transmit_byte(8'h55);

        // Test 2: Transmit 0x00 (all zeros)
        $display("\n--- Test 2: 0x00 ---");
        transmit_byte(8'h00);

        // Test 3: Transmit 0xFF (all ones)
        $display("\n--- Test 3: 0xFF ---");
        transmit_byte(8'hFF);

        // Test 4: Transmit 0xA5 (alternating, inverted)
        $display("\n--- Test 4: 0xA5 ---");
        transmit_byte(8'hA5);

        // Test 5: Transmit 0x3C
        $display("\n--- Test 5: 0x3C ---");
        transmit_byte(8'h3C);

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

    // Timeout watchdog
    initial begin
        #(CLK_PERIOD * 100000);
        $display("ERROR: Simulation timeout");
        $finish;
    end

endmodule
