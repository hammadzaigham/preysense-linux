"""Pure RAPL Tau encoding audit helpers; no hardware writes.

Windows PreySense labels encoded 0x7f as infinity, but it is the longest
representable finite window. Linux powercap uses integer microseconds.
"""
TAU_STEPS=(0,1,2,4,8,16,32,56,64,128,256,449)
INFINITY_SELECTION=449

def decode_us(code,time_unit_us):
    if type(code) is not int or not 0<=code<=127:raise ValueError('Tau code must be 0–127')
    if type(time_unit_us) is not int or time_unit_us<=0:raise ValueError('Time unit must be positive integer microseconds')
    return (1<<(code&31))*(4+((code>>5)&3))*time_unit_us//4

def linux_encode_us(value,time_unit_us):
    """Match intel_rapl_common.c rapl_default_compute_time_window(to_raw)."""
    if type(value) is not int or value<0:raise ValueError('Tau request must be nonnegative integer microseconds')
    if type(time_unit_us) is not int or time_unit_us<=0:raise ValueError('Time unit must be positive integer microseconds')
    if value<time_unit_us:return 0
    value//=time_unit_us
    exponent=value.bit_length()-1
    if exponent>31:return 127
    fraction=4*(value-(1<<exponent))//(1<<exponent)
    return exponent|((fraction&3)<<5)

def infer_unit_us(code,readback_us):
    """Infer only when the current encoded value and sysfs readback agree exactly."""
    decode_us(code,1)  # Validate the encoded input before using its bit fields.
    numerator=(1<<(code&31))*(4+((code>>5)&3))
    if type(readback_us) is not int or readback_us<=0 or (readback_us*4)%numerator:
        raise ValueError('Cannot infer an exact kernel time unit from this snapshot')
    unit=readback_us*4//numerator
    # Common Core conversion from USEC_PER_SEC >> unit exponent.
    if unit not in {1000000>>exponent for exponent in range(16)} or unit<=0:
        raise ValueError('Unexpected kernel RAPL time unit')
    if decode_us(code,unit)!=readback_us:raise ValueError('Inconsistent Tau readback')
    return unit

def windows_endpoint_request_us(selection,time_unit_us):
    """Request Linux values reproducing Windows minimum/code1 or max/code127.

These values are not automatically applied. Callers must capture/restore both
RAPL domains, verify the raw code and report that max is finite (~42 days here).
"""
    if selection not in (0,INFINITY_SELECTION):raise ValueError('Expected Windows minimum or infinity selection')
    code=1 if selection==0 else 127
    request=decode_us(code,time_unit_us)
    if linux_encode_us(request,time_unit_us)!=code:raise ValueError('Endpoint does not roundtrip through Linux encoding')
    return request
