from collections.abc import Sequence

# Type hints for configuration parameters

CONFIG_FILE: str

def load(path: str = ...) -> None: ...

BPM_list_file: str
BPM_pattern: str
BPM_id_range: range
ORBIT_DETUNE: int
ATTENUATOR_LIST: Sequence[tuple[int, int]]
BPMS_no_current: list[str]
ISCALE_DCCT_THRESHOLD: int
ISCALE_SCALING_K: float
ISCALE_TIMER_INTERVAL: int
LTB_THRESHOLD: float
BTS_THRESHOLD: float
BCD_LIMIT: int
BCD_SLEW_INTERVAL: float
BCD_SLEW_RATE: int
BCD_SHORT_LENGTH: float
BCD_LONG_LENGTH: float
BCD_SPECIAL_LENGTHS: dict[str, float]
BCD_SPECIAL_CENTRES: dict[str, float]
