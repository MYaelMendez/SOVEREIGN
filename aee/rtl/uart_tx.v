// AEE RTL-001: UART Transmitter  (revision 2 — SIM gate fix)
// SPEC-001 → RTL
// æ:// Agentic Electronic Engineering
// Target: iCE40 HX8K
// Author: Yæl Méndez
//
// Revision 2 — defects found by the SIM gate (rev 1 failed: data bits = x, Test 2 timeout):
//   B1  tx_ready was an undriven wire (x)          → assign tx_ready = !fifo_full
//   B2  tx_byte <= fifo_rd_data raced the FIFO read (data sampled as x)
//       → FSM pops fifo[rd_ptr] combinationally at the moment it leaves IDLE
//   B3  WAIT state held baud_cnt at 0 → could never complete (Test 2 hung)
//       → WAIT removed; STOP returns directly to IDLE
//   B4  FIFO count/read keyed off FSM state redundantly → single rd_en term

module uart_tx #(
    parameter FIFO_DEPTH = 16,
    parameter FIFO_AW    = 4          // log2(FIFO_DEPTH)
)(
    input  wire            clk,
    input  wire            rst_n,

    // TX data interface
    input  wire [7:0]      tx_data,
    input  wire            tx_valid,
    output wire            tx_ready,

    // Serial output
    output reg             tx,

    // Configuration
    input  wire [15:0]     baud_div,

    // Status
    output wire [FIFO_AW:0] fifo_count,
    output wire            fifo_full,
    output wire            fifo_empty
);

    // ─── FIFO storage ───
    reg [7:0]         fifo [0:FIFO_DEPTH-1];
    reg [FIFO_AW-1:0] wr_ptr, rd_ptr;
    reg [FIFO_AW:0]   count;

    assign fifo_count = count;
    assign fifo_full  = (count == FIFO_DEPTH);
    assign fifo_empty = (count == 0);
    assign tx_ready   = !fifo_full;                 // B1: was undriven

    // ─── Transmit FSM ───
    localparam IDLE = 2'd0, START = 2'd1, DATA = 2'd2, STOP = 2'd3;
    reg [1:0]  state;
    reg [15:0] baud_cnt;
    reg [3:0]  bit_idx;
    reg [7:0]  shift_reg;

    wire wr_en    = tx_valid && !fifo_full;
    wire rd_en    = (state == IDLE) && !fifo_empty;  // B4: single read enable
    wire bit_done = (baud_cnt == baud_div - 16'd1);

    // ─── FIFO write ───
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= {FIFO_AW{1'b0}};
        end else if (wr_en) begin
            fifo[wr_ptr] <= tx_data;
            wr_ptr       <= wr_ptr + 1'b1;
        end
    end

    // ─── FIFO read pointer ───
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_ptr <= {FIFO_AW{1'b0}};
        end else if (rd_en) begin
            rd_ptr <= rd_ptr + 1'b1;
        end
    end

    // ─── FIFO occupancy ───
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) count <= 0;
        else case ({wr_en, rd_en})
            2'b10:   count <= count + 1'b1;
            2'b01:   count <= count - 1'b1;
            default: count <= count;
        endcase
    end

    // ─── Baud counter ───
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)             baud_cnt <= 0;
        else if (state == IDLE) baud_cnt <= 0;
        else if (bit_done)      baud_cnt <= 0;
        else                    baud_cnt <= baud_cnt + 1'b1;
    end

    // ─── FSM ───
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= IDLE;
            tx        <= 1'b1;
            bit_idx   <= 4'd0;
            shift_reg <= 8'd0;
        end else begin
            case (state)
                IDLE: begin
                    tx <= 1'b1;
                    if (!fifo_empty) begin
                        shift_reg <= fifo[rd_ptr];   // B2: combinational pop — no stale race
                        bit_idx   <= 4'd0;
                        state     <= START;
                    end
                end

                START: begin
                    tx <= 1'b0;                      // start bit
                    if (bit_done) state <= DATA;
                end

                DATA: begin
                    tx <= shift_reg[0];              // LSB first
                    if (bit_done) begin
                        shift_reg <= {1'b0, shift_reg[7:1]};
                        if (bit_idx == 4'd7) state   <= STOP;
                        else                 bit_idx <= bit_idx + 1'b1;
                    end
                end

                STOP: begin
                    tx <= 1'b1;                      // stop bit
                    if (bit_done) state <= IDLE;     // B3: no dead WAIT state
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
