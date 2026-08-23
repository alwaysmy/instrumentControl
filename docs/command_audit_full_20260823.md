# SCPI 全量审计（代码 vs 手册）

## dh1766

- [HIT ] `*CLS` @ dh1766_control\src\dh1766_control\commands.py:17
- [HIT ] `*ESE` @ dh1766_control\src\dh1766_control\commands.py:18
- [HIT ] `*ESR?` @ dh1766_control\src\dh1766_control\commands.py:19
- [HIT ] `*IDN?` @ dh1766_control\src\dh1766_control\commands.py:20
- [HIT ] `*OPC` @ dh1766_control\src\dh1766_control\commands.py:21
- [HIT ] `*PSC` @ dh1766_control\src\dh1766_control\commands.py:22
- [HIT ] `*RST` @ dh1766_control\src\dh1766_control\commands.py:23
- [HIT ] `*SRE` @ dh1766_control\src\dh1766_control\commands.py:24
- [HIT ] `*STB?` @ dh1766_control\src\dh1766_control\commands.py:25
- [HIT ] `*TRG` @ dh1766_control\src\dh1766_control\commands.py:26
- [HIT ] `:ALL?` @ dh1766_control\src\dh1766_control\dh1766.py:351

## dho

- [**MISS**] `:CLEar` @ dho_control\commands.py:15
- [HIT ] `:RUN` @ dho_control\commands.py:16
- [HIT ] `:STOP` @ dho_control\commands.py:17
- [**MISS**] `:SINGle` @ dho_control\commands.py:18
- [**MISS**] `:TFORce` @ dho_control\commands.py:19
- [HIT ] `:AUToset` @ dho_control\commands.py:20
- [HIT ] `:TRIGger:MODE` @ dho_control\commands.py:23
- [HIT ] `:TRIGger:STATus?` @ dho_control\commands.py:24
- [HIT ] `:TRIGger:SWEep` @ dho_control\commands.py:25
- [HIT ] `:TRIGger:COUPling` @ dho_control\commands.py:26
- [HIT ] `:TRIGger:EDGE:SOURce` @ dho_control\commands.py:27
- [HIT ] `:TRIGger:EDGE:SLOPe` @ dho_control\commands.py:28
- [HIT ] `:TRIGger:EDGE:LEVel` @ dho_control\commands.py:29
- [HIT ] `:ACQuire:MDEPth` @ dho_control\commands.py:32
- [HIT ] `:ACQuire:TYPE` @ dho_control\commands.py:33
- [HIT ] `:ACQuire:SRATe?` @ dho_control\commands.py:34
- [HIT ] `:CHANnel{n}:DISPlay` @ dho_control\commands.py:37
- [HIT ] `:CHANnel{n}:COUPling` @ dho_control\commands.py:38
- [HIT ] `:CHANnel{n}:VERNier` @ dho_control\commands.py:39
- [HIT ] `:CHANnel{n}:INVert` @ dho_control\commands.py:40
- [HIT ] `:CHANnel{n}:BWLimit` @ dho_control\commands.py:41
- [HIT ] `:CHANnel{n}:SCALe` @ dho_control\commands.py:42
- [HIT ] `:CHANnel{n}:OFFSet` @ dho_control\commands.py:43
- [HIT ] `:CHANnel{n}:PROBe` @ dho_control\commands.py:44
- [HIT ] `:CHANnel{n}:UNITs` @ dho_control\commands.py:45
- [HIT ] `:TIMebase:MAIN:SCALe` @ dho_control\commands.py:48
- [HIT ] `:TIMebase:MAIN:OFFSet` @ dho_control\commands.py:49
- [HIT ] `:MEASure:ITEM` @ dho_control\commands.py:52
- [HIT ] `:MEASure:CLEar` @ dho_control\commands.py:53
- [HIT ] `:WAVeform:SOURce` @ dho_control\commands.py:56
- [HIT ] `:WAVeform:MODE` @ dho_control\commands.py:57
- [HIT ] `:WAVeform:FORMat` @ dho_control\commands.py:58
- [HIT ] `:WAVeform:POINts` @ dho_control\commands.py:59
- [HIT ] `:WAVeform:STARt` @ dho_control\commands.py:60
- [HIT ] `:WAVeform:STOP` @ dho_control\commands.py:61
- [HIT ] `:WAVeform:DATA?` @ dho_control\commands.py:62
- [HIT ] `:WAVeform:XINCrement?` @ dho_control\commands.py:63
- [HIT ] `:WAVeform:XORigin?` @ dho_control\commands.py:64
- [HIT ] `:WAVeform:YINCrement?` @ dho_control\commands.py:65
- [HIT ] `:WAVeform:YORigin?` @ dho_control\commands.py:66
- [HIT ] `:WAVeform:YREFerence?` @ dho_control\commands.py:67
- [HIT ] `:SYSTem:ERRor?` @ dho_control\commands.py:70
- [HIT ] `:SYSTem:VERSion?` @ dho_control\commands.py:71
- [HIT ] `:SYSTem:RESet` @ dho_control\commands.py:72
- [HIT ] `:SYSTem:BEEPer` @ dho_control\commands.py:73
- [HIT ] `*IDN?` @ dho_control\dho.py:108

## sds

- [HIT ] `:MEASure:SIMPle:SOURce C4` @ TEST_SCRIPTS\common\sds_simple_meas.py:37
- [**MISS**] `:SYST:ERR?` @ TEST_SCRIPTS\common\sds_simple_meas.py:43
- [HIT ] `:RUN` @ sds_control\commands.py:14
- [HIT ] `:STOP` @ sds_control\commands.py:15
- [**MISS**] `:AUTOSET` @ sds_control\commands.py:16
- [HIT ] `:TRIGger:STATus?` @ sds_control\commands.py:34
- [HIT ] `:MEASure:ADVanced:CLEar` @ sds_control\commands.py:42
- [HIT ] `:MEASure:ADVanced:P{n}:TYPE?` @ sds_control\commands.py:43
- [HIT ] `:MEASure:ADVanced:P{n}:VALue?` @ sds_control\commands.py:45
- [HIT ] `:WAVeform:SOURce` @ sds_control\commands.py:47
- [HIT ] `:WAVeform:PREamble?` @ sds_control\commands.py:48
- [HIT ] `:WAVeform:MAXPoint?` @ sds_control\commands.py:49
- [HIT ] `:WAVeform:STARt` @ sds_control\commands.py:50
- [HIT ] `:WAVeform:POINt` @ sds_control\commands.py:51
- [HIT ] `:WAVeform:WIDTh` @ sds_control\commands.py:52
- [HIT ] `*IDN?` @ sds_control\sds.py:112
- [HIT ] `:MEASure:MODE SIMPle` @ sds_control\sds.py:233
- [HIT ] `:MEASure:SIMPle:ITEM {item},ON` @ sds_control\sds.py:240

## sdg

- [**MISS**] `:SYST:ERR?` @ sdg_control\commands.py:19
- [**MISS**] `:SYST:VERS?` @ sdg_control\commands.py:20
- [HIT ] `*IDN?` @ sdg_control\sdg.py:81

## k3446x

- [**MISS**] `:CONF?` @ TEST_SCRIPTS\common\probe_new_instruments.py:28
- [**MISS**] `:MEAS:VOLT:DC?` @ TEST_SCRIPTS\common\probe_new_instruments.py:29
- [**MISS**] `:SYST:ERR?` @ TEST_SCRIPTS\common\probe_new_instruments.py:38
- [HIT ] `*OPC?` @ TEST_SCRIPTS\common\probe_new_instruments.py:38
- [**MISS**] `:MEAS:VOLT:AC?` @ keysight_3446x\commands.py:16
- [**MISS**] `:MEAS:CURR:DC?` @ keysight_3446x\commands.py:17
- [**MISS**] `:MEAS:CURR:AC?` @ keysight_3446x\commands.py:18
- [**MISS**] `:MEAS:RES?` @ keysight_3446x\commands.py:19
- [**MISS**] `:MEAS:FRES?` @ keysight_3446x\commands.py:20
- [**MISS**] `:MEAS:CONT?` @ keysight_3446x\commands.py:21
- [**MISS**] `:MEAS:CAP?` @ keysight_3446x\commands.py:22
- [**MISS**] `:MEAS:DIOD?` @ keysight_3446x\commands.py:23
- [**MISS**] `:MEAS:FREQ?` @ keysight_3446x\commands.py:24
- [HIT ] `:READ?` @ keysight_3446x\commands.py:25
- [**MISS**] `:CONF:VOLT:DC` @ keysight_3446x\commands.py:28
- [**MISS**] `:CONF:VOLT:AC` @ keysight_3446x\commands.py:29
- [**MISS**] `:CONF:RES` @ keysight_3446x\commands.py:30
- [**MISS**] `:CONF:FREQ` @ keysight_3446x\commands.py:31
- [**MISS**] `:SENS:VOLT:DC:NPLC` @ keysight_3446x\commands.py:33
- [**MISS**] `:SENS:VOLT:DC:APER` @ keysight_3446x\commands.py:34
- [**MISS**] `:SENS:COUN` @ keysight_3446x\commands.py:35
- [**MISS**] `:TRIG:SOUR` @ keysight_3446x\commands.py:36
- [**MISS**] `:DATA:LAST?` @ keysight_3446x\commands.py:38
- [**MISS**] `:STAT:PRES` @ keysight_3446x\commands.py:39
- [HIT ] `*IDN?` @ keysight_3446x\commands.py:8
- [HIT ] `*OPT?` @ keysight_3446x\commands.py:9
- [**MISS**] `:CONF:X` @ keysight_3446x\dmm.py:151
