"""

@author: Javier

2024
"""

import pyvisa
import numpy as np
import time


class AgilentOSA:
    def __init__(self, address= 'GPIB0::23::INSTR', timeout = 40000):
        self.rm = pyvisa.ResourceManager()
        self.Agilent = self.rm.open_resource(address)
        self.Agilent.timeout = timeout  # ms

        # Definitions of the device parameters allowed ranges
        self.y_units = 'dBm'
        self.x_units = 'nm'
        self.min_wl, self.max_wl = 600 , 1700 
        self.min_resolution, self.max_resolution = 0.06 , 10
        self.min_ref_level, self.max_ref_level = -90 , 20 
        self.min_trace_points, self.max_trace_points = 11, 10001
        self.min_sensitivity, self.max_sensitivity = -90 , 0
        self.Agilent.write('*RST')
        self.start = np.nan
        self.stop = np.nan
        self.ref_level = np.nan
        self.resolution = np.nan
        self.sensitivity = np.nan
        self.trace_points = np.nan


    def set_start(self, start):
        assert start >= self.min_wl and start <= self.max_wl
        self.Agilent.write(f'SENSe:WAVelength:STARt {start:.2f} nm')
        self.start = start

    def set_stop(self, stop):
        assert stop >= self.min_wl and stop <= self.max_wl
        self.Agilent.write(f'SENSe:WAVelength:STOP {stop:.2f} nm')
        self.stop = stop

    def set_ref(self, ref_level):
        assert ref_level >= self.min_ref_level and  ref_level <= self.max_ref_level
        self.Agilent.write(f'DISPlay:WINDow:TRACe:Y:SCALe:RLEVel {ref_level:.2f} dBm')
        self.ref_level = ref_level

    def set_resolution(self, resolution):
        assert resolution >= self.min_resolution and resolution <= self.max_resolution
        self.Agilent.write(f'BWIDth:RESolution {resolution:.2f} nm')
        self.resolution = resolution


    def sensitivity_mode(self, sensitivity):
        assert sensitivity >= self.min_sensitivity and sensitivity <= self.max_sensitivity
        self.Agilent.write(f'SENSe:POWer:DC:RANGe:LOWer {sensitivity:.2f} dBm')
        self.sensitivity = sensitivity

    def set_trace_points(self, trace_points):
        assert trace_points >= self.min_trace_points and trace_points <= self.max_trace_points
        self.Agilent.write(f'SENSe:SWEep:POINts {trace_points}')
        self.trace_points = trace_points        

    def get_wavlength_range(self):
        return self.min_wl, self.max_wl

    def get_resolution_range(self):
        return self.min_resolution, self.max_resolution

    def get_ref_level_range(self):
        return self.min_ref_level, self.max_ref_level

    def get_trace_points_range(self):
        return self.min_trace_points, self.max_trace_points

    def get_sensitivities(self):
        return self.min_sensitivity, self.max_sensitivity
    
    def get_id(self):
        return self.Agilent.query('*IDN?')

    def get_trace(self):
        self.Agilent.write('INITIATE:IMMEDIATE')
        data_str = self.Agilent.query('trace:data:y? TrA')
        data_list = data_str.split(',')
        # Convert each element to a float
        power = [float(num) for num in data_list]
        wavelength = (np.linspace(self.start, self.stop, self.trace_points)).tolist()
        dict_results = {
            'wavelength': wavelength, 
            'power': power  
        }
        return dict_results
    
    def write(self, command):
        self.Agilent.write(command)

    def query(self, command):
        self.Agilent.query(command)