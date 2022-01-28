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
from enum import IntEnum
import numpy as np
import sys


class Keithley6514(Device):
    MEAS_RANGES = ['auto', '20e-12', '200e-12', '2e-9', '20e-9', '200e-9',
                   '2e-6', '20e-6', '200e-6', '2e-3', '20e-3']

    current = attribute(
        name='current',
        access=READ,
        unit='A',
        dtype=tango.DevFloat,
        format='%10.4f',
        )
    
    measrange = attribute(
        name='range',
        access=READ_WRITE,
        dtype=tango.DevEnum,
        label='measurement range',
        enum_labels=MEAS_RANGES,
        )
   
    gpib_addr = device_property(dtype=str, mandatory=True, update_db=True)
    
    def init_device(self):
        Device.init_device(self)
        self.rm = pyvisa.ResourceManager('@py')
        self.inst = self.rm.open_resource(f'GPIB::{self.gpib_addr}::INSTR')
        try:
            ans = self.inst.query('*IDN?')
            print(ans)
            if 'MODEL 6514' in ans:
                self.reset_device()
                self.source_setup()
                self._range = 0
                self._current = 0
                self.set_state(DevState.ON)
            else:
                self.set_state(DevState.FAULT)
                sys.exit(255)
        except Exception as e:
            print(e, file=self.log_error)
            self.inst.close()
            self.set_state(DevState.FAULT)
            sys.exit(255)
    
    def read_current(self):
        ans = self.inst.query('READ?')
        ans = ans.split(',')[0]
        print('read current:', ans, file=self.log_debug)
        return float(ans)
    
    def read_range(self):
        return self._range
    
    def write_range(self, value):
        rangestr = self.MEAS_RANGES[value]
        print('set range:', rangestr, file=self.log_debug)
        if value == 0:
            self.inst.write('SENS:CURR:RANG:AUTO ON')
        else:
            range_float = float(rangestr)
            self.inst.write(f'SENS:CURR:RANG {range_float}')
        self._range = value
    
    def source_setup(self):
        self.inst.write('SYST:ZCH ON')
        self.inst.write('FUNC "CURR"')
        self.inst.write('CURR:NPLC 1')
        self.inst.write('CURR:RANG:AUTO ON')
        self.inst.write('SYST:ZCOR ON')
        self.inst.write('SYST:ZCH OFF')
            
    @command
    def reset_device(self):
        self.inst.write('*RST')
        self.inst.write('*CLS')
        self.source_setup()
        
           

if __name__ == "__main__":
    Keithley6514.run_server()
