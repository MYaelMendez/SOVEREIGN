// AEE RTL-002: UART Receiver
// SPEC-002 → RTL-002
// æ:// Agentic Electronic Engineering
// Mirrors: uart_tx (RTL-001)

module uart_rx #(
    parameter BAUD_DIV_WIDTH = 16,
    parameter DATA_WIDTH = 8
)(
    input  wire                  clk,
    input  wire                  rst_n,

    // RX data interface
    input  wire [BAUD_DIV_WIDTH-1:0] baud_div,
    output reg  [DATA_WIDTH-1:0]     rx_data,
    output reg                       rx_valid,
    input  wire                      rx_ready,

    // Serial input
    input  wire                      rx,

    // Error flags
    output reg                       parity_error,
    output reg                       frame_error
);

    // ─── Oversampling ───
    reg [3:0] sample_cnt;
    reg [BAUD_DIV_WIDTH-1:0] baud_cnt;
    reg [2:0] sample_history;

    // ─── State Machine ───
    localparam IDLE    = 3'b000;
    localparam START   = 3'b001;
    localparam DATA    = 3'b010;
    localparam STOP    = 3'b011;
    localparam ERROR   = 3'b100;

    reg [2:0] state;
    reg [2:0] next_state;
    reg [2:0] bit_idx;

    // ─── Start bit detection ───
    reg rx_d1, rx_d2;
    wire start_edge;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_d1 <= 1'b1;
            rx_d2 <= 1'b1;
        end else begin
            rx_d1 <= rx;
            rx_d2 <= rx_d1;
        end
    end

    assign start_edge = rx_d2 & ~rx_d1;  // Falling edge

    // ─── Baud counter ───
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            baud_cnt <= 0;
            sample_cnt <= 0;
        end else begin
            if (state == IDLE && start_edge) begin
                baud_cnt <= 0;
                sample_cnt <= 0;
            end else if (baud_cnt >= baud_div - 1) begin
                baud_cnt <= 0;
                sample_cnt <= sample_cnt + 1;
            end else begin
                baud_cnt <= baud_cnt + 1;
            end
        end
    end

    // ─── Sampling ───
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_history <= 3'b000;
        end else if (state != IDLE && state != ERROR) begin
            sample_history <= {sample_history[1:0], rx};
        end
    end

    // ─── Shift register ───
    reg [7:0] shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bit_idx <= 0;
            shift_reg <= 0;
            rx_data <= 0;
            rx_valid <= 0;
            parity_error <= 0;
            frame_error <= 0;
            state <= IDLE;
        end else begin
            case (state)
                IDLE:
                    rx_valid <= 0;
                    parity_error <= 0;
                    frame_error <= 0;
                    if (start_edge)
                        state <= START;

                START:
                    // Wait for baud_div/2 to sample start bit
                    if (sample_cnt >= 7 && baud_cnt >= baud_div/2 - 1) begin
                        // Confirm start bit (3 samples via majority)
                        if (sample_history[2] == 0) begin
                            state <= DATA;
                            bit_idx <= 0;
                        end else begin
                            state <= IDLE;  // False start
                        end
                    end

                DATA:
                    if (baud_cnt >= baud_div - 1 && sample_cnt >= 7) begin
                        shift_reg <= {rx, shift_reg[7:1]};
                        if (bit_idx == 7) begin
                            bit_idx <= 0;
                            state <= STOP;
                            rx_data <= {rx, shift_reg[7:1]};
                        end else begin
                            bit_idx <= bit_idx + 1;
                        end
                    end

                STOP:
                    if (baud_cnt >= baud_div - 1 && sample_cnt >= 7) begin
                        if (rx == 1'b1) begin
                            rx_valid <= 1;
                            state <= IDLE;
                        end else begin
                            frame_error <= 1;
                            state <= ERROR;
                        end
                    end

                ERROR:
                    rx_valid <= 0;
                    state <= IDLE;

                default: state <= IDLE;
            endcase
        end
    end

endmodule
