# Loads list of BPMs

import re

import numpy

from . import config


# Loads list of ids and bpms from BPM list file.
def load_bpm_list():
    match = re.compile(config.BPM_pattern)
    range = set(config.BPM_id_range)
    for line in open(config.BPM_list_file).readlines():
        if line and line[0] != "#":
            id_bpm = line.split()
            if len(id_bpm) >= 2:
                id, bpm = id_bpm[:2]
                id = int(id)
                if id in range and match.match(bpm):
                    yield (id, bpm)


# Performs sanity check on bpm_list: essentially all ids must be contiguous and
# in order, so this is particularly easy to check.
def validate_bpm_list(bpm_list):
    ids = numpy.array([id for id, bpm in bpm_list])
    assert (numpy.diff(ids) == 1).all()


# Converts a BPM name into a BPM position ID.  This is designed entirely for
# visual convenience, so to each BPM we assign a decimal position ID of the form
# c.n.  For normal arc BPMs c is the cell number and n the BPM number, for the
# straights we assign ids (c-1).9 and c.0.  Hacky, but it seems to work ok.
split_pattern = re.compile("SR(..)(.)-DI-EBPM-(..)")


def make_bpm_id(bpm):
    m = split_pattern.match(bpm)
    if not m:
        raise ValueError(f"Invalid BPM name: {bpm!r}")
    cell, place, num = m.groups()
    cell = int(cell)
    assert place in "CS"
    num = int(num)
    if place == "C":
        return cell + 0.1 * num
    else:
        return cell + 0.1 * num - 0.2


BPM_list: list = []
BPMS: list = []
BPM_count: int = 0
BPM_ids: list = []
BPM_name_id: dict = {}


def load() -> None:
    global BPM_list, BPMS, BPM_count, BPM_ids, BPM_name_id

    # Load (id, bpm) list from file
    BPM_list = list(load_bpm_list())
    validate_bpm_list(BPM_list)

    # List of all BPMs in order around the ring.
    BPMS = [bpm for id, bpm in BPM_list]
    BPM_count = len(BPMS)
    BPM_ids = list(map(make_bpm_id, BPMS))

    # Mapping from BPM name to BPM id
    BPM_name_id = {bpm: id for id, bpm in BPM_list}


# Converts a BPM specific PV into one PV per BPM.
def bpm_pvs(name):
    return [f"{bpm}:{name}" for bpm in BPMS]
