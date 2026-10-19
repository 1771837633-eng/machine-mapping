#pragma TextEncoding = "UTF-8"
#pragma rtGlobals=3
#pragma IndependentModule=MMMapping

// Synthetic, independent expectations: affine angular intensity and an analytic
// energy integral. No experimental data and no installed library dependencies.
Function MM_SelfTest(tag)
    String tag
    DFREF before=GetDataFolderDFR()
    String source="root:MMValidation:"+tag+":",dest="root:MMResults:"+tag
    Variable i,e=-0.0031,det=4.7,theta=-6.5,beta,t,k0,kx,ky,xv,yv,value,expected,maxError=0,count=0,code=0
    if(DataFolderExists(source) || DataFolderExists(dest))
        MM_Fail("Self-test name is already used.")
    endif
    NewDataFolder/O root:MMValidation
    NewDataFolder/S $(RemoveEnding(source,":"))
    NewDataFolder/S OriginalData
    Make/T/N=3 OriginalImage={"testA","testB","testC"},ProcessedImage={"syn0","syn1","syn2"}
    Make/D/N=3 Theta_Angle={-8,0,-4},Phi_Angle=2,BiasVoltage=0
    SetDataFolder $source
    NewDataFolder/S PROCESS
    Variable/G PhotonEnergy=6.994,WorkFunction=4.8,LatticeConstant=3.68
    Variable/G ThetaOffset=1.3,PhiOffset=-0.7,RotationAngle=17,DetectorCenterAngle=0.8
    Make/D/N=(11,9) syn0,syn1,syn2
    SetScale/P x -.01,.002,"eV",syn0,syn1,syn2
    SetScale/P y -12,3,"deg",syn0,syn1,syn2
    syn0=1000+7*x+3*y+5*(-8)
    syn1=1000+7*x+3*y
    syn2=1000+7*x+3*y+5*(-4)
    Make/FREE/D angles={-8,-4,0}
    Make/FREE/T names={"syn0","syn2","syn1"}
    // Forward reference uses polar rotation, as in the original table routine.
    k0=.5118*3.68/3.1416*sqrt(6.994-4.8+e)
    beta=(.8-det+2-(-.7))*pi/180
    t=(theta-1.3)*pi/180
    kx=k0*sin(beta); ky=k0*sin(t)*cos(beta)
    xv=sqrt(kx*kx+ky*ky)*cos(atan2(ky,kx)+17*pi/180)
    yv=sqrt(kx*kx+ky*ky)*sin(atan2(ky,kx)+17*pi/180)
    value=MM_Pixel(e,xv,yv,source,angles,names,6.994,4.8,3.68,1.3,-.7,2,17,.8)
    expected=1000+7*e+3*det+5*theta
    if(numtype(value)!=0 || abs(value-expected)>1e-9)
        MM_Fail("Synthetic rotated angular interpolation failed.")
    endif
    if(numtype(MM_Pixel(e,9,9,source,angles,names,6.994,4.8,3.68,1.3,-.7,2,17,.8))!=2)
        MM_Fail("Unmeasured momentum must be NaN.")
    endif
    syn0=1000+7*x; syn1=1000+7*x; syn2=1000+7*x
    MM_Run(source,dest,"testA;testB;testC;","-8;0;-4;",-.0035,.0045,17,13,6.994)
    Wave fs=$(dest+":FermiSurface"),zero=$(dest+":ZeroEnergySlice"),mask=$(dest+":Coverage")
    expected=1000*(.0045-(-.0035))+3.5*(.0045^2-(-.0035)^2)
    for(i=0;i<numpnts(fs);i+=1)
        if(numtype(fs[i])==0)
            maxError=max(maxError,abs(fs[i]-expected))
            count+=1
        endif
        if(numtype(zero[i])==0 && abs(zero[i]-1000)>1e-9)
            MM_Fail("Synthetic EF slice failed.")
        endif
    endfor
    if(count<5 || maxError>1e-9 || WaveMin(mask)!=0 || WaveMax(mask)!=1)
        MM_Fail("Synthetic clipped trapezoid integration or coverage failed.")
    endif
    SetDataFolder before
    try
        MM_Run(source,dest+"Bad","testA;testB;testC;","NaN;0;-4;",-.0035,.0045,17,13,6.994)
    catch
        code=V_AbortCode
        Variable err=GetRTError(1)
    endtry
    if(code!=100 || !DataFolderRefsEqual(before,GetDataFolderDFR()))
        MM_Fail("Invalid angle guard or data folder restoration failed.")
    endif
    Print "MM_SELFTEST_PASS: rotated interpolation; NaN coverage; shuffled CUT identity; analytic clipped integral; EF slice; CRC; invalid angle; restored folder",maxError,count
End
