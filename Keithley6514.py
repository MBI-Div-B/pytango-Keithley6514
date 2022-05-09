#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 14 14:39:56 2020

@author: Michael Schneider <mschneid@mbi-berlin.de>, Max Born Institut Berlin

This is a rudimentary driver to enable diode current measurements
"""


import pyvisa
import tango
from tango import DevState
from tango.server import Device, attribute, command
from tango.server import device_property
from tango import READ, READ_WRITE
import numpy as np
import sys
from enum import IntEnum, Enum


class TriggerMode(IntEnum):
    AUTO = 0
    EXTERNAL = 1


class Keithley6514(Device):
    MEAS_RANGES = [
        "auto",
        "20e-12",
        "200e-12",
        "2e-9",
        "20e-9",
        "200e-9",
        "2e-6",
        "20e-6",
        "200e-6",
        "2e-3",
        "20e-3",
    ]

    zerocheck = attribute(
        label="zerocheck",
        access=READ_WRITE,
        dtype=bool,
        )

    speed = attribute(
        label="speed (NPLC)",
        access=READ_WRITE,
        dtype=float,
        min_value=0.01,
        max_value=10,
        doc=("Integration time in number of power line cycles.\n"
             "Device defaults are SLOW (5), MEDIUM (1) and FAST (0.1)\n")
        )

    current = attribute(
        name="current",
        access=READ,
        unit="A",
        dtype=float,
        format="%6.4e",
    )

    measrange = attribute(
        name="range",
        access=READ_WRITE,
        dtype=tango.DevEnum,
        label="measurement range",
        enum_labels=MEAS_RANGES,
    )

    trigger = attribute(
        label="trigger mode",
        access=READ_WRITE,
        dtype=TriggerMode,
        )

    gpib_addr = device_property(dtype=str, mandatory=True, update_db=True)

    def init_device(self):
        Device.init_device(self)
        self.rm = pyvisa.ResourceManager("@py")
        self.inst = self.rm.open_resource(f"GPIB::{self.gpib_addr}::INSTR")
        self.inst.read_termination = '\n'
        self.inst.write_termination = '\n'
        self.inst.clear()
        try:
            ans = self.inst.query("*IDN?")
            print(ans)
            if "MODEL 6514" in ans:
                self._trigger = TriggerMode.AUTO
                self.reset_device()
                self.set_state(DevState.ON)
            else:
                self.set_state(DevState.FAULT)
                sys.exit(255)
        except Exception as e:
            print(e, file=self.log_error)
            self.inst.close()
            self.set_state(DevState.FAULT)
            sys.exit(255)

    def always_executed_hook(self):
        # print(f"always_executed_hook: {ans}", file=self.log_debug)
        pass

    def read_current(self):
        if self._trigger == TriggerMode.AUTO:
            # trigger and request fresh reading
            ans = self.inst.query_ascii_values("READ?")
        else:
            # external trigger - just return last reading
            ans = self.inst.query_ascii_values("FETCH?")
        return ans[0]

    def read_range(self):
        return self._range

    def read_speed(self):
        return self._speed

    def write_speed(self, nplc):
        self.inst.write(f"CURR:NPLC {nplc:.2f}")
        self._speed = nplc

    def read_trigger(self):
        return self._trigger

    def write_trigger(self, mode):
        if mode == TriggerMode.AUTO:
            self.inst.write("TRIG:SOUR IMM")
        elif mode == TriggerMode.EXTERNAL:
            self.inst.write("TRIG:SOUR TLIN")
        self._trigger = mode

    def write_range(self, value):
        rangestr = self.MEAS_RANGES[value]
        print(f"set range: {rangestr}", file=self.log_debug)
        if value == 0:
            self.inst.write("SENS:CURR:RANG:AUTO ON")
        else:
            self.inst.write(f"SENS:CURR:RANG {rangestr}")
        self._range = value

    def read_zerocheck(self):
        return self._zch

    def write_zerocheck(self, zch):
        mode = "ON" if zch else "OFF"
        self.inst.write(f"SYST:ZCH {mode}")
        self._zch = zch

    def source_setup(self):
        commands = [
            "SYST:ZCH ON",
            "FUNC 'CURR'",
            "CURR:RANG:AUTO ON",
            "SYST:ZCOR ON",
            "FORM:ELEM READ,TIME",
            "TRAC:TST:FORM DELT",
            "ARM:SOUR IMM",
            ]
        for cmd in commands:
            self.inst.write(cmd)
        self._zch = True
        self._range = 0
        self.write_speed(1)

    @command(dtype_in=str, dtype_out=str)
    def query_device(self, msg):
        ans = self.inst.query(msg)
        return ans

    @command(dtype_in=str)
    def write_to_device(self, msg):
        self.inst.write(msg)

    @command
    def reset_device(self):
        self.inst.write("*RST")
        self.inst.write("*CLS")
        self.source_setup()

    @command(dtype_in=int)
    def configure_buffer(self, num):
        """Store up to <num> raw readings and time stamps in buffer.
        Storing starts immediately, so trigger should be configured first.
        """
        print(f"Enabling data buffer with size {num}", file=self.log_debug)
        commands = [
            "TRAC:CLE",
            f"TRAC:POIN {num:d}",
            "TRAC:FEED SENS",
            "TRAC:FEED:CONT NEXT",
            ]
        for cmd in commands:
            self.inst.write(cmd)

    @command(dtype_out=(float,))
    def read_buffer(self):
        """Return stored data from buffer."""
        count = int(self.inst.query("TRAC:POIN:ACT?"))
        if count > 0:
            data = np.array(self.inst.query_ascii_values("TRAC:DATA?"))
            print(f"Read buffer: {count}", file=self.log_debug)
        else:
            data = np.array([-1, -1])
            print(f"Read buffer: empty!", file=self.log_warn)
        return data

    @command(dtype_out=str)
    def read_and_clear_errors(self):
        ans = self.inst.query("SYST:ERR:ALL?")
        return ans



if __name__ == "__main__":
    Keithley6514.run_server()
