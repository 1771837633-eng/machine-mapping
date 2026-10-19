#pragma TextEncoding = "UTF-8"
#pragma rtGlobals=3
#pragma IndependentModule=MMMapping

// Data-only local inbox. No Execute of request text, no /X, no new instance.
// This file and MMMomentum.ipf belong to the same independent module.
Function/S MM_Line(ref)
    Variable ref
    String line
    FReadLine ref,line
    return ReplaceString("\n",ReplaceString("\r",line,""),"")
End

Function MM_Heartbeat(busy)
    String busy
    SVAR dir=root:MMMappingState:BridgeDirectory
    SVAR session=root:MMMappingState:BridgeSession
    Variable ref
    Open ref as dir+"ready.txt"
    fprintf ref,"MM1\r\n%s\r\n%.0f\r\n%s\r\n",session,DateTime,busy
    Close ref
End

Function MM_StartBridge(directory,session)
    String directory,session
    if(cmpstr(StringByKey("IGORKIND",IgorInfo(0)),"pro64")!=0)
        MM_Fail("Use the user's existing 64-bit Igor instance.")
    endif
    if(strlen(directory)<4 || cmpstr(directory[strlen(directory)-1],":")!=0 || !GrepString(session,"^[a-f0-9]{32}$"))
        MM_Fail("Invalid bridge directory or session.")
    endif
    NewDataFolder/O root:MMMappingState
    String/G root:MMMappingState:BridgeDirectory=directory
    String/G root:MMMappingState:BridgeSession=session
    String/G root:MMMappingState:LastJob=""
    MM_Heartbeat("")
    CtrlNamedBackground MMNotebook,period=120,proc=MMMapping#MM_Poll,start
    Print "MM_BRIDGE_READY",directory
End

Function MM_StopBridge()
    CtrlNamedBackground MMNotebook,stop
    MM_Heartbeat("stopped")
End

Function MM_LoadSource(pxp,base,cuts)
    String pxp,base,cuts
    Variable i,j,row
    String objects="PhotonEnergy;WorkFunction;LatticeConstant;ThetaOffset;PhiOffset;RotationAngle;DetectorCenterAngle;",cut
    if(DataFolderExists(base))
        MM_Fail("Input folder already exists; never overwrite a previous trial.")
    endif
    GetFileFolderInfo/Q/Z pxp
    if(V_flag!=0 || !V_isFile)
        MM_Fail("Source PXP is missing.")
    endif
    NewDataFolder/S $(RemoveEnding(base,":"))
    NewDataFolder/S OriginalData
    LoadData/Q/S="root:OriginalData"/J="OriginalImage;ProcessedImage;Theta_Angle;Phi_Angle;BiasVoltage;" pxp; AbortOnRTE
    Wave/T originals=OriginalImage,processed=ProcessedImage; AbortOnRTE
    Wave phis=Phi_Angle; AbortOnRTE
    for(i=0;i<ItemsInList(cuts);i+=1)
        cut=StringFromList(i,cuts)
        row=-1
        for(j=0;j<numpnts(originals);j+=1)
            if(cmpstr(originals[j],cut)==0)
                if(row>=0)
                    MM_Fail("Duplicate original CUT identity.")
                endif
                row=j
            endif
        endfor
        if(row<0 || row>=numpnts(processed))
            MM_Fail("CUT identity absent from PXP metadata.")
        endif
        if(row>=numpnts(phis) || numtype(phis[row])!=0 || abs(phis[row])>1e-8)
            MM_Fail("Notebook pilot requires source phi=0; motor mapping is not calibrated.")
        endif
        objects+=processed[row]+";"
    endfor
    if(strlen(objects)>1999)
        MM_Fail("Too many CUT names for selective LoadData; split this scan.")
    endif
    SetDataFolder $base
    NewDataFolder/S PROCESS
    LoadData/Q/S="root:PROCESS"/J=objects pxp; AbortOnRTE
End

Function MM_Receipt(job,status,destination,message)
    String job,status,destination,message
    SVAR dir=root:MMMappingState:BridgeDirectory
    Variable ref,ne=0,nx=0,ny=0,finite=0,nans=0,residual=0
    if(cmpstr(status,"memory_complete")==0)
        Wave cube=$(destination+":EKxKy")
        NVAR error=$(destination+":RoundtripMaxAbs")
        ne=DimSize(cube,0); nx=DimSize(cube,1); ny=DimSize(cube,2)
        WaveStats/Q cube
        finite=V_npnts; nans=V_numNaNs; residual=error
    endif
    message=ReplaceString("\n",ReplaceString("\r",message," ")," ")
    Open ref as dir+job+".receipt.txt"
    fprintf ref,"MM1\r\n%s\r\n%s\r\n%s\r\n%s\r\n%d\r\n%d\r\n%d\r\n%.0f\r\n%.0f\r\n%.17g\r\nEND\r\n",job,status,destination,message,ne,nx,ny,finite,nans,residual
    Close ref
End

Function MM_Poll(s)
    STRUCT WMBackgroundStruct &s
    DFREF before=GetDataFolderDFR()
    SVAR dir=root:MMMappingState:BridgeDirectory
    SVAR session=root:MMMappingState:BridgeSession
    SVAR last=root:MMMappingState:LastJob
    Variable ref,err,code,low,high,nx,ny,hv,i
    String version,token,job,pxp,cuts,angles,base,destination,message
    // Missing request is normal. An incomplete file cannot appear: Python renames it.
    Open/R/Z ref as dir+"request.txt"
    if(V_flag!=0)
        MM_Heartbeat("")
        return 0
    endif
    version=MM_Line(ref); token=MM_Line(ref); job=MM_Line(ref)
    if(cmpstr(version,"MM1")!=0 || cmpstr(token,session)!=0 || !GrepString(job,"^[a-f0-9]{16}$") || cmpstr(job,last)==0)
        Close ref
        MM_Heartbeat("")
        return 0
    endif
    pxp=MM_Line(ref); cuts=MM_Line(ref); angles=MM_Line(ref)
    low=str2num(MM_Line(ref)); high=str2num(MM_Line(ref))
    nx=str2num(MM_Line(ref)); ny=str2num(MM_Line(ref)); hv=str2num(MM_Line(ref))
    Close ref
    last=job
    base="root:MMInput_"+job+":"
    destination="root:MMResults:j"+job
    MM_Heartbeat(job)
    String/G root:MMMappingState:LastError=""
    try
        if(ItemsInList(cuts)<2 || ItemsInList(cuts)!=ItemsInList(angles) || numtype(low+high+nx+ny+hv)!=0)
            MM_Fail("Invalid request fields.")
        endif
        for(i=0;i<ItemsInList(cuts);i+=1)
            if(!GrepString(StringFromList(i,cuts),"^[A-Za-z_][A-Za-z0-9_]{0,30}$"))
                MM_Fail("Invalid CUT identifier.")
            endif
        endfor
        MM_LoadSource(pxp,base,cuts); AbortOnRTE
        MM_Run(base,destination,cuts,angles,low,high,nx,ny,hv); AbortOnRTE
        MM_Receipt(job,"memory_complete",destination,"Memory trial complete; calibration unverified.")
    catch
        code=V_AbortCode
        message=GetRTErrMessage()
        err=GetRTError(1)
        SVAR detail=root:MMMappingState:LastError
        if(strlen(detail)>0)
            message=detail
        elseif(err==0)
            message="Interrupted or aborted ("+num2str(code)+")"
        endif
        MM_Receipt(job,"failed",destination,message)
    endtry
    SetDataFolder before
    MM_Heartbeat("")
    return 0
End
