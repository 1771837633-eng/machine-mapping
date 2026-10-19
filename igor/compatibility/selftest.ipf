#pragma TextEncoding = "UTF-8"
#pragma rtGlobals=3

// Synthetic software checks only; no experimental input or physical calibration.
Function MMRepairSelfTest()
    Make/FREE/D/N=3 a={1,2,3}
    Variable n=JEG_ReverseLegacy(a)
    if(n!=3 || a[0]!=3 || a[1]!=2 || a[2]!=1)
        Abort "Legacy reverse failed for default scaling"
    endif
    a={1,2,3}
    SetScale/P x,5,2,a
    n=JEG_ReverseLegacy(a)
    if(n!=3 || a[0]!=3 || a[1]!=2 || a[2]!=1 || DimOffset(a,0)!=5 || DimDelta(a,0)!=2)
        Abort "Legacy reverse failed for nondefault scaling"
    endif
    Make/FREE/D/N=0 empty
    n=JEG_ReverseLegacy(empty)
    if(n!=0 || numpnts(empty)!=0)
        Abort "Legacy reverse failed for empty input"
    endif
    Make/FREE/D/N=2 b={4,5}
    a={1,2,3}
    NewDataFolder/O root:MMRepairSmoke20261019
    n=JEG_ConcatenateLegacy(a,b,"root:MMRepairSmoke20261019:joined","")
    Wave joined=root:MMRepairSmoke20261019:joined
    if(n!=5 || numpnts(joined)!=5 || joined[0]!=1 || joined[1]!=2 || joined[2]!=3 || joined[3]!=4 || joined[4]!=5)
        Abort "Legacy concatenate failed"
    endif
    if(a[0]!=1 || a[1]!=2 || a[2]!=3 || b[0]!=4 || b[1]!=5)
        Abort "Legacy concatenate changed an input"
    endif
    if(WinType("ARPES_Analysis")!=7 || WinType("FitFermiLevel")!=7)
        Abort "Startup panels are absent"
    endif
    Variable caught=0, err=0
    if(exists("BCSEDC")==0)
        try
            WDS_convFunc_BCSfit(a,b,b)
        catch
            caught=1
            err=GetRTError(1)
        endtry
        if(!caught || b[0]!=4 || b[1]!=5)
            Abort "Missing BCSEDC did not fail before changing input"
        endif
    endif
    caught=0
    if(exists("BCSEDC_Direct")==0)
        try
            WDS_convFunc_BCSfit2(a,b,b)
        catch
            caught=1
            err=GetRTError(1)
        endtry
        if(!caught || b[0]!=4 || b[1]!=5)
            Abort "Missing BCSEDC_Direct did not fail before changing input"
        endif
    endif
    Print "MM_LEGACY_SELFTEST_PASS: reverse/default/scaled/empty; concatenate; two startup panels; missing BCS guards"
    return 0
End
