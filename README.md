[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# concentrator

The Diagnostics Concentrator performs two key functions:

• Readings from all storage ring BPMs are collected together into waveforms indexed by BPM id. \
• Centralised control of all storage ring BPMs is provided through a number of simple controls.

Source          | <https://gitlab.diamond.ac.uk/controls/ioc/CS/cs-di-ioc-01>
:---:           | :---:
Docker          | `docker run ghcr.io/diamondlightsource/concentrator:latest`
Releases        | <https://gitlab.diamond.ac.uk/controls/ioc/CS/cs-di-ioc-01/releases>


The concentrator can be started as:

```
python -m concentrator
```

## PVs

All PVs provided by the concentrator are of the form `SR-DI-EBPM-01:`\<name>.
The following names are of particular interest:

### Key Process Variables

**`SA:X`, `SA:Y`**  
Beam position around the storage ring.

**`MAXADC_PC`**  
Maximum ADC reading across all BPMs as a percentage of the maximum possible reading.

**`ATTENUATION_S`**  
Sets attenuation values for all BPMs. The special setting "Auto" enables automatic incrementing or decrease of attenuators as the `MAXADC_PC` value rises or falls.

**`AUTOBCD`**  
Controls the management of BCD ("Beam Current Dependency") values written to all storage ring BPMs.

**`MODE_S`**  
Switches between "Orbit" and "Tune" modes:

- **"Orbit"** - Normal machine operation with switches running and BPM detuned. Provides most accurate position measurement, but adds high frequency artifacts to measured beam.
- **"Tune"** - Switches disabled and detune set to zero. Intended for use with machine physics measurements.

## Files

**`concentrator.py`**  
Top level startup script, configures imports, loads remaining components, runs interactive IOC shell.

**`config.py`**  
Loads configuration file.

**`bpm_list.py`**  
Loads list of SR BPMs from BPM list file.

**`autocurrent.py`**  
Monitors and updates `CF:ISCALE_S` to keep EBPM signal in step with DCCT signal.

**`bcd.py`**  
No longer manages BCD (misnomer), but implements autogain functionality. Should be renamed to `autogain.py`.

**`enabled.py`**  
Monitors SA positions and ENABLED flags, computes health waveform by taking missed updates into account.

**`maxadc.py`**  
Manages distributed waveforms with special processing for `SA:MAXADC`.

**`intervals.py`**  
Complex code for gathering distributed updates into common intervals. New functionality designed to be used throughout concentrator.

**`monitor.py`**  
PV monitoring support, should mostly be obsoleted by `intervals.py`.

**`injection.py`**  
New transfer efficiency calculations.

**`interlock.py`**
Now cut to the bone, can be merged and dropped.

**`booster.py`**  
Initial ideas for booster concentrator PVs. Booster-specific PV implementations should go here.

**`updater.py`**  
Manages collections of updating waveforms.

**`sa_waveforms.py`**  
Initial implementation of SA waveforms not currently used.

## Concentrated Waveforms

### BS-DI Triggered Waveforms
- `FR:{STD,PP}{X,Y}` - Fast readout data

### PM Triggered Waveforms  
- `PM:{X,Y,ADC}_{OFL,OFFSET}` - Post-mortem data (OFFSET values need special offset processing)

### SA Waveforms
- `SA:{CURRENT,X,Y,MAXADC}` - Slow acquisition data (MAXADC needs maximal severity)

### Asynchronous Controls
- `CF:ISCALE_S` - Current scaling
- `{FT,FR,BN,IL}:ENABLE_S` - Enable controls
- `CF:{ATTEN,AUTOSW,DETUNE}_S` - Configuration controls

## Interval Controller

### Class Hierarchy

```
autosuper
├── ControllerBase
│   ├── IntervalController
│   └── TriggeredController
├── ValueBase
│   ├── Value
│   │   └── Value_PV
│   └── Waveform
│       └── Waveform_PV (Internal waveform from list of PVs)
│           ├── Waveform_Out (Published waveform from PV list)
│           └── MaskedWaveform
├── IrregularController
├── Controller_extra
├── UpdateValue (Internal to ValueBase)
├── UpdateWaveform (Internal to ValueBase)
└── Waveform_Mean
```

## Complete PV List

### System Information
**`CS-DI-IOC-01:`**
- `HOSTNAME`
- `WHOAMI`

### Main Control Interface
**`SR-DI-EBPM-01:`**

#### Attenuation Control
- `ATTENUATION:STAT`
- `ATTENUATION_S`
- `ATTENUATOR:DOWN`
- `ATTENUATOR:UP`

#### System Status
- `BPMID`
- `COUNT_DISABLED`
- `COUNT_ENABLED`  
- `COUNT_UNREACHABLE`
- `ENABLED`

#### Current Scaling
- `ISCALE_INTERVAL`
- `ISCALE_K`
- `ISCALE_MIN`

#### ADC Monitoring
- `MAXADC`
- `MAXADCID`
- `MAXADCWF`
- `MAXADC_PC`

#### Mode Control
- `MODE:STAT`
- `MODE_S`

#### Subsystem Enable Controls
- `{BN,FR,FT}:ENABLE{,_S,:STAT}`
- `IL:ENABLE`

#### Configuration Controls
- `CF:{ATTEN,AUTOSW,DSC,GOLDEN_{X,Y}}{,_S,:STAT}`
- `CK:DETUNE{,_S,:STAT}`

#### Beam Position Data
- `SA:CURRENT{,:MEAN}`
- `SA:{X,Y}{,:{{MIN,MAX}{,WF},MEAN,RESET,STD}}`

#### Fast Readout (BS-DI triggered, normally 5Hz)
- `FR:{PP,STD}{X,Y}`

#### Post-Mortem Data (PM triggered, OFFSET values adjusted before publishing)
- `PM:{ADC,X,Y}_{OFFSET,OFL}`

#### Statistical Data
- `SA:CURRENT{,:MEAN}`
- `SA:{X,Y}:{{MAX,MIN}{,WF},MEAN,RESET,STD}`
