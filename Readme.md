# Keithley 6514
Minimal device server that uses the Keithley 6514 Electrometer to measure
currents.

## Installation
requires pyvisa and a working GPIB installation

## Configuration
Only device property is the GPIB address. It's inserted in the following pyvisa
device string:

`f'GPIB::{gpib_address}::INSTR'`

## Authors
M. Schneider, MBI Berlin
