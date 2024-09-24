
"""

@author: Javier

2024
"""

import pyvisa
import numpy as np
import time
from pint import UnitRegistry
ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = ureg.Quantity

rm = pyvisa.ResourceManager()
# print(rm.list_resources())

#Definitions of the device parammeters allowed ranges
min_wl, max_wl = 600* ureg.nm, 1750 * ureg.nm
min_resolution, max_resolution = 0.01*ureg.nm, 2*ureg.nm
min_ref_level, max_ref_level = -90*ureg.dBm, 20*ureg.dBm
min_trace_points, max_trace_points = 11, 20001
sensitivities = ['SNHD', 'SNAT', 'SHI1', 'SHI2', 'SHI3']
sens_dict = {
            'SNHD': 'Hold',
            'SNAT': 'Auto',
            'SHI1': 'High 1',
            'SHI2': 'High 2',
            'SHI3': 'High 3'
        }


def connect_to_osa(address = 'GPIB0::3::INSTR'):
    ANDO = rm.open_resource(address)
    ANDO.timeout = 40000 #ms

def update_params(updated_params):
    """updated_params is a dictonary with the parameters to be updated, if a parameter is not in the dictonary, it will be ignored"""
    if 'trace' in updated_params:
        trace = updated_params['trace']
    else:
        trace = 'A'  # Default value if 'trace' is not in the dictionary
    #Trace has to be A,B or C 
    assert trace in ('A','B','C')
    active_trace(trace)

    if 'start' in updated_params and 'stop' in updated_params:
        start = updated_params['start']
        if type(start) is ureg.Quantity:
            start = start.to(ureg.nm).magnitude
        set_start(start)
        
    if 'stop' in updated_params:
        stop = updated_params['stop']
        if type(stop) is ureg.Quantity:
            stop = stop.to(ureg.nm).magnitude
        set_stop(stop)

    if 'ref_level' in updated_params:
        ref = updated_params['ref_level']
        if type(ref) is ureg.Quantity:
            ref = ref.to(ureg.dBm).magnitude
        set_ref(ref)

    if 'resolution' in updated_params:
        resolution = updated_params['resolution']
        if type(resolution) is ureg.Quantity:
            resolution = resolution.to(ureg.nm).magnitude
        set_resolution(resolution)

    if 'sensitivity' in updated_params:
        sensitivity_mode(updated_params['sensitivity'])
    
    if 'trace_points' in updated_params:
        set_trace_points(updated_params['trace_points'])

def get_trace():
    #Perform a sweep
    ANDO.query('SGL')
    #Ensure that the sweep is finished
    sweep_status = ANDO.query('SWEEP?')
    while sweep_status != '0':
        time.sleep(1)
        sweep_status = ANDO.query('SWEEP?')
    #Get the wavelength data
    wl_read = ANDO.query('WDAT'+trace).strip().split(',')
    wl = wl_read[1:]
    # list of strings -> numpy array (vector) of floats
    wl = np.asarray(wl,'f').T
    points_read_wl = wl_read[0].split(' ')[-1]
    assert int(points_read_wl) == len(wl)
    
    #Get the power data
    power_read = ANDO.query('LDAT'+trace).strip().split(',')
    power = power_read.split(',')[1:]
    power = np.asarray(power,'f').T
    points_read_power = power_read[0].split(' ')[-1]
    assert int(points_read_power) == len(power)
    spectrum_data = {
        'wavelength': Q_(wl,  ureg.nm),
        'power': Q_(power , ureg.dBm),
    }
    return spectrum_data

def set_start(start):
    assert start>=600 and start<=1750
    ANDO.query(f'STAWL{start:.2f}')
    rec_start = ANDO.query('STAWL?')
    assert float(rec_start.strip()) == start, f'Start wavelength not set correctly, expected {start}, got {rec_start}'

def set_stop(stop):
    assert stop>=600 and stop<=1750
    ANDO.query(f'STPWL{stop:.2f}')
    rec_stop = ANDO.query('STPWL?')
    assert float(rec_stop.strip()) == stop, f'Stop wavelength not set correctly, expected {stop}, got {rec_stop}'

def set_ref(ref_level):
    assert ref_level>=-90 and ref_level<=20
    ANDO.query(f'REFL{ref_level:.1f}')
    rec_ref = ANDO.query('REFL?')
    assert float(rec_ref.strip()) == ref_level, f'Reference level not set correctly, expected {ref_level}, got {rec_ref}'

def set_resolution(resolution):
    assert resolution>=0.01 and resolution<=2.0
    ANDO.query(f'RESLN{resolution:.2f}')
    rec_res = ANDO.query('RESLN?')
    assert float(rec_res.strip()) == resolution, f'Resolution not set correctly, expected {resolution}, got {rec_res}'

def active_trace(trace):
    assert trace in ('A','B','C')
    ANDO.query(f'ACTV{trace}')

def sensitivity_mode(sensitivity):
    assert sensitivity in ('SNHD', 'SNAT', 'SHI1', 'SHI2', 'SHI3')
    ANDO.query(sensitivity)

def set_trace_points(trace_points):
    assert trace_points>=11 and trace_points<=20001
    ANDO.query(f'SMPL{trace_points}')
    rec_points = ANDO.query('SMPL?')
    assert int(rec_points.strip()) == trace_points, f'Trace points not set correctly, expected {trace_points}, got {rec_points}'


def get_wavlength_range():
    return min_wl, max_wl
def get_resolution_range():
    return min_resolution, max_resolution
def get_ref_level_range():
    return min_ref_level, max_ref_level
def get_trace_points_range():
    return min_trace_points, max_trace_points
def get_sensitivities():
    return sensitivities
def get_sensitivities_dict():
    return sens_dict

