# Concentrator waveforms for the booster and injection paths.


def BRpvs(name):
    return ['BR%02dC-DI-EBPM-%02d:%s' %
        (((2*n + 6) // 11) % 4 + 1, n + 1, name)
        for n in range(23)]

def LBpvs(name):
    return ['LB-DI-EBPM-%02d:%s' % (n + 1, name) for n in range(7)]

def BSpvs(name):
    return ['BS-DI-EBPM-%02d:%s' % (n + 1, name) for n in range(7)]


# List of Booster PVs to concentrate

BOOSTER_CONTROL = [
    'CF:BBA_X_S', 'CF:BBA_Y_S',
    'FT:ENABLE_S', 'FR:ENABLE_S', 'BN:ENABLE_S', 'MS:ENABLE_S',
    'CF:ATTEN_S', 'CF:ATTEN:DISP_S', 'CF:ATTEN:AGC_S',
]
