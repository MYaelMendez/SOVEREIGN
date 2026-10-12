// AEE RTL-001: UART Transmitter
// SPEC-001 → RTL
// æ:// Agentic Electronic Engineering
// Target: iCE40 HX8K
// Author: Yæl Méndez
// Date: 2026-10-08

module uart_tx #(
    parameter FIFO_DEPTH = 16,
    parameter FIFO_AW = 4  // log2(FIFO_DEPTH)
)(
    input  wire        clk,
    input  wire        rst_n,

    // TX data interface
    input  wire [7:0]  tx_data,
    input  wire        tx_valid,
    output wire        tx_ready,

    // Serial output
    output reg         tx,

    // Configuration
    input  wire [15:0] baud_div,

    // Status
    output wire [FIFO_AW:0] fifo_count,
    output wire        fifo_full,
    output wire        fifo_empty
);

    // ─── FIFO ───
    reg [7:0] fifo [0:FIFO_DEPTH-1];
    reg [FIFO_AW-1:0] wr_ptr;
    reg [FIFO_AW-1:0] rd_ptr;
    reg [FIFO_AW:0]   count;

    assign fifo_count = count;
    assign fifo_full  = (count == FIFO_DEPTH);
    assign fifo_empty = (count == 0);

    // Write to FIFO
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 0;
        end else if (tx_valid && !fifo_full) begin
            fifo[wr_ptr] <= tx_data;
            wr_ptr <= wr_ptr + 1;
        end
    end

    // Read from FIFO
    reg [7:0] fifo_rd_data;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_ptr <= 0;
        end else if (rd_ptr != wr_ptr && !fifo_empty) begin
            fifo_rd_data <= fifo[rd_ptr];
            rd_ptr <= rd_ptr + 1;
        end
    end

    // ─── TX State Machine ───
    localparam IDLE  = 3'b000;
    localparam START = 3'b001;
    localparam DATA  = 3'b010;
    localparam STOP  = 3'b011;
    localparam WAIT  = 3'b100;

    reg [2:0] state;
    reg [15:0] baud_cnt;
    reg [2:0] bit_idx;
    reg [7:0] shift_reg;
    reg [7:0] tx_byte;

    // Baud rate counter
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            baud_cnt <= 0;
        end else if (state == IDLE || state == WAIT) begin
            baud_cnt <= 0;
        end else if (baud_cnt == baud_div - 1) begin
            baud_cnt <= 0;
        end else begin
            baud_cnt <= baud_cnt + 1;
        end
    end

    // Main state machine
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            tx <= 1'b1;
            bit_idx <= 0;
            shift_reg <= 0;
            tx_byte <= 0;
        end else begin
            case (state)
                IDLE: begin
                    tx <= 1'b1;
                    if (!fifo_empty) begin
                        tx_byte <= fifo_rd_data;
                        state <= START;
                    end
                end

                START: begin
                    tx <= 1'b0;  // Start bit
                    if (baud_cnt == baud_div - 1) begin
                        shift_reg <= tx_byte;
                        bit_idx <= 0;
                        state <= DATA;
                    end
                end

                DATA: begin
                    tx <= shift_reg[0];
                    if (baud_cnt == baud_div - 1) begin
                        shift_reg <= {1'b0, shift_reg[7:1]};
                        if (bit_idx == 7) begin
                            state <= STOP;
                        end else begin
                            bit_idx <= bit_idx + 1;
                        end
                    end
                end

                STOP: begin
                    tx <= 1'b1;  // Stop bit
                    if (baud_cnt == baud_div - 1) begin
                        state <= WAIT;
                    end
                end

                WAIT: begin
                    tx <= 1'b1;
                    if (baud_cnt == baud_div - 1) begin
                        state <= IDLE;
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end

    // FIFO read logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 0;
        end else begin
            case ({tx_valid && !fifo_full, state == IDLE && !fifo_empty})
                2'b10: count <= count + 1;
                2'b01: count <= count - 1;
                2'b11: count <= count;
                default: count <= count;
            endcase
        end
    end

endmodule
