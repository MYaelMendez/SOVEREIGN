# AEE SPEC-002: UART Receiver
# SPEC-001 → SPEC-002 (dual, shared bus)
# æ:// Agentic Electronic Engineering
# Author: Yæl Méndez
# Date: 2026-10-08
# Target: iCE40 HX8K (Lattice)
# Toolchain: iverilog → yosys → nextpnr-ice40

## 1. Overview

A UART receiver that mirrors SPEC-001 (uart_tx). Together they form a full-duplex
UART with shared bus interface. Receiver samples at 16x baud, detects start bit,
samples data at bit center, and detects stop bit.

## 2. Interface

### 2.1 Clock and Reset
- `clk` — system clock (50 MHz target)
- `rst_n` — active-low asynchronous reset

### 2.2 RX Data Interface
- `rx_data[7:0]` — received byte (valid when `rx_valid` is high)
- `rx_valid` — data valid (pulse for 1 clock)
- `rx_ready` — flow control (high = ready to accept)

### 2.3 Serial Input
- `rx` — UART RX line (idle high)

### 2.4 Configuration
- `baud_div[15:0]` — baud rate divider (clk_freq / baud_rate)

## 3. Protocol

### 3.1 Frame Detection
- Idle state: `rx` high
- Start bit: `rx` transitions high→low
- Data bits: 8 bits, LSB first, sampled at bit center
- Stop bit: `rx` must be high at bit center of stop bit position

### 3.2 Oversampling
- 16x oversampling for noise immunity
- Sample at baud_div/2 after edge detection
- Confirm start bit by checking 3 consecutive samples

### 3.3 Error Detection
- `parity_error` — if parity bit doesn't match
- `frame_error` — if stop bit is not high

## 4. Timing

### 4.1 Sampling
- Sample at counter = baud_div/2, then every baud_div clocks
- Total sample period: 16 samples per bit

### 4.2 Throughput
- Max: 1 byte per 10 bit periods
- At 115200 baud: ~4340 clocks/byte

## 5. Verification

### 5.1 Testbench
- Receive 0x55 (alternating 01010101)
- Receive 0x00 (8 zero bits)
- Receive 0xFF (8 one bits)
- Inject start bit late by 1 sample → verify recovery
- Inject stop bit error → verify frame_error

### 5.2 Synthesis Target
- Device: iCE40 HX8K (CT256)
- Max frequency: > 50 MHz
- LUT utilization: < 100

## 6. Receipt

SPEC-002 → SHA256 → receipt
Prev: `ae://receipt/aee-spec-001-6d2d6be292f6141e`
