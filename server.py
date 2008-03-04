'''Wrapper for channel access server.'''

import signal

from dls.ca2 import catools
from dls.cas import cas, server

import dls.green as green



# Translates some of the slightly daft CA attribute names into more familiar
# names (or, rather, vice versa, in this case).
_TranslateName = {
    'low'  : 'graphicLow',
    'high' : 'graphicHigh'
}


# Default PV change handler to block unwanted writes
def _ForbidChange(pv, value):
    print 'Write', value, 'to', pv.name, 'rejected'
    return False


def Create(name, value,
        changed=None, device='SR-DI-EBPM-01', enums=None,
        **extras):

    # If no changed handler is specified then block all changes.
    if changed is None:  changed = _ForbidChange
    
    pv = _Server.create('%s:%s' % (device, name), value, changed)
    if enums is not None:
        pv.enums = enums
        pv.type_code = cas.aitEnumEnum16
    for name, value in extras.items():
        if name in _TranslateName:  name = _TranslateName[name]
        setattr(pv, name, value)
    return pv


def Timer(interval, action):
    server.timer(interval, action)


def RunServer():
    server.run()
    print 'server finished'



def _ServiceTimer(t):
    catools.ca_pend_event(1e-9)
    green.tick()


# transform blocking catools into co-operative
catools.install_sleep(green.co_sleep)

# Create the master server instance
_Server = server.Server(debug=True)

# Ensure that we have at least a fighting chance to exit cleanly.
signal.signal(signal.SIGINT, lambda *_: server.quit())

# Tie together the server, catools and the greenlets framework.
Timer(0.01, _ServiceTimer)
