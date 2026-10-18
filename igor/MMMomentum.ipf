#pragma TextEncoding = "UTF-8"
#pragma rtGlobals=3

// Memory-only prototype. Geometry follows GetEKxKyIntenTable in
// 16XJZGetEKxKyIntensityTable.ipf, not the old angle-stacking 3D macro.
// Restricted to zero bias, common phi and a common detector/energy grid.
// No writes to source waves, global PROCESS settings, or experiment files.

Function MM_Pixel(e, kx, ky, source, theta, names, hv, workf, lc, toff, poff, phi0, rotation, center)
    Variable e,kx,ky,hv,workf,lc,toff,poff,phi0,rotation,center
    String source
    Wave theta
    Wave/T names
    Variable rad=pi/180, k0=0.5118*lc/3.1416*sqrt(hv-workf+e)
    Variable xx=kx*cos(rotation*rad)+ky*sin(rotation*rad)
    Variable yy=-kx*sin(rotation*rad)+ky*cos(rotation*rad)
    if(k0<=0 || abs(xx/k0)>=1)
        return NaN
    endif
    Variable beta=asin(xx/k0)
    if(abs(yy/(k0*cos(beta)))>1)
        return NaN
    endif
    Variable t=asin(yy/(k0*cos(beta)))/rad+toff
    Variable det=center+phi0-poff-beta/rad
    Variable n=numpnts(theta), j
    if(t<theta[0]-1e-8 || t>theta[n-1]+1e-8)
        return NaN
    endif
    t=max(theta[0],min(theta[n-1],t))
    for(j=0;j<n-1;j+=1)
        if(t<=theta[j+1]+1e-8)
            break
        endif
    endfor
    j=min(j,n-2)
    Wave w0=$(source+"PROCESS:"+names[j])
    Wave w1=$(source+"PROCESS:"+names[j+1])
    Variable d0=DimOffset(w0,1), d1=d0+(DimSize(w0,1)-1)*DimDelta(w0,1)
    if(det<min(d0,d1)-1e-8 || det>max(d0,d1)+1e-8)
        return NaN
    endif
    det=max(min(d0,d1),min(max(d0,d1),det))
    Variable f=(t-theta[j])/(theta[j+1]-theta[j])
    return (1-f)*interp2D(w0,e,det)+f*interp2D(w1,e,det)
End

Function MM_Run(source, destination, cuts, expectedTheta, low, high, nx, ny, expectedHV)
    String source,destination,cuts,expectedTheta
    Variable low,high,nx,ny,expectedHV
    DFREF saved=GetDataFolderDFR()
    Variable n=ItemsInList(cuts), i,j,row,ne,nd,ee,ix,iy,c,dt
    Variable hv,workf,lc,toff,poff,rotation,center,phi0,e0,de,d0,dd
    Variable k0,beta,t,kx,ky,xmin=Inf,xmax=-Inf,ymin=Inf,ymax=-Inf
    Variable a,b,va,vb,total,valid,p0,p1,frac,xv,yv,ev,actual,residual=0
    String cut,pname
    if(n<2 || n!=ItemsInList(expectedTheta) || nx<3 || ny<3 || nx>301 || ny>301 || low>=high)
        Abort "Invalid scan list, grid, or integration window."
    endif
    if(DataFolderExists(destination))
        Abort "Result folder exists. Use a new job ID to preserve previous results."
    endif
    Wave/T originals=$(source+"OriginalData:OriginalImage")
    Wave/T processed=$(source+"OriginalData:ProcessedImage")
    Wave angles=$(source+"OriginalData:Theta_Angle")
    Wave phis=$(source+"OriginalData:Phi_Angle")
    Wave bias=$(source+"OriginalData:BiasVoltage")
    hv=NumVarOrDefault(source+"PROCESS:PhotonEnergy",NaN)
    workf=NumVarOrDefault(source+"PROCESS:WorkFunction",NaN)
    lc=NumVarOrDefault(source+"PROCESS:LatticeConstant",NaN)
    toff=NumVarOrDefault(source+"PROCESS:ThetaOffset",NaN)
    poff=NumVarOrDefault(source+"PROCESS:PhiOffset",NaN)
    rotation=NumVarOrDefault(source+"PROCESS:RotationAngle",NaN)
    center=NumVarOrDefault(source+"PROCESS:DetectorCenterAngle",NaN)
    if(numtype(hv+workf+lc+toff+poff+rotation+center)!=0 || hv<=workf || lc<=0)
        Abort "Missing or invalid momentum geometry."
    endif
    if(abs(hv-expectedHV)>1e-8)
        Abort "Source photon energy disagrees with notebook scan manifest."
    endif
    NewDataFolder/O root:MMResults
    NewDataFolder/S $destination
    Make/D/N=(n) Theta,SourceRows,SourceSums
    Make/T/N=(n) Names,OriginalNames
    for(i=0;i<n;i+=1)
        cut=StringFromList(i,cuts)
        row=-1
        for(j=0;j<numpnts(originals);j+=1)
            if(cmpstr(cut,originals[j])==0)
                if(row>=0)
                    Abort "Duplicate source identity."
                endif
                row=j
            endif
        endfor
        if(row<0)
            Abort "Requested CUT is missing from source parameter table."
        endif
        if(abs(angles[row]-str2num(StringFromList(i,expectedTheta)))>1e-8 || numtype(angles[row])!=0)
            Abort "Current angle disagrees with the explicit scan manifest."
        endif
        if(abs(bias[row])>1e-8 || numtype(bias[row])!=0)
            Abort "This prototype does not implement biased ARPES geometry."
        endif
        if(i==0)
            phi0=phis[row]
        endif
        if(abs(phi0-phis[row])>1e-8 || numtype(phis[row])!=0)
            Abort "This prototype requires common phi."
        endif
        pname=processed[row]
        Wave/Z w=$(source+"PROCESS:"+pname)
        if(!WaveExists(w) || WaveDims(w)!=2)
            Abort "Missing processed 2D CUT. Raw-file preprocessing is not implemented by this prototype."
        endif
        if(i==0)
            ne=DimSize(w,0); nd=DimSize(w,1)
            e0=DimOffset(w,0); de=DimDelta(w,0)
            d0=DimOffset(w,1); dd=DimDelta(w,1)
        endif
        if(DimSize(w,0)!=ne || DimSize(w,1)!=nd || abs(DimOffset(w,0)-e0)>1e-10 || abs(DimDelta(w,0)-de)>1e-10 || abs(DimOffset(w,1)-d0)>1e-10 || abs(DimDelta(w,1)-dd)>1e-10)
            Abort "Processed CUT grids differ."
        endif
        WaveStats/Q w
        if(V_numNaNs>0 || V_numINFs>0)
            Abort "Source contains non-finite intensity."
        endif
        Theta[i]=angles[row]; SourceRows[i]=row; SourceSums[i]=V_sum
        Names[i]=pname; OriginalNames[i]=cut
    endfor
    if(de<=0 || ne<2 || nd<2 || dd==0 || low<e0-1e-9 || high>e0+de*(ne-1)+1e-9)
        Abort "Integration window is outside processed energy coverage."
    endif
    Sort Theta,Theta,Names,OriginalNames,SourceRows,SourceSums
    for(i=1;i<n;i+=1)
        if(Theta[i]-Theta[i-1]<1e-8)
            Abort "Duplicate scan angle."
        endif
    endfor
    // Envelope of actual sampling. Unmeasured pixels remain NaN at each energy.
    for(ee=0;ee<2;ee+=1)
        ev=e0+ee*de*(ne-1)
        k0=0.5118*lc/3.1416*sqrt(hv-workf+ev)
        for(i=0;i<n;i+=1)
            t=(Theta[i]-toff)*pi/180
            for(j=0;j<nd;j+=1)
                beta=(center-d0-dd*j+phi0-poff)*pi/180
                if(abs(beta)>=pi/2 || abs(t)>=pi/2)
                    Abort "Geometry outside supported inverse branches."
                endif
                kx=k0*sin(beta); ky=k0*sin(t)*cos(beta)
                xv=kx*cos(rotation*pi/180)-ky*sin(rotation*pi/180)
                yv=kx*sin(rotation*pi/180)+ky*cos(rotation*pi/180)
                xmin=min(xmin,xv); xmax=max(xmax,xv)
                ymin=min(ymin,yv); ymax=max(ymax,yv)
            endfor
        endfor
    endfor
    if(xmax<=xmin || ymax<=ymin || ne*nx*ny>20000000)
        Abort "Degenerate or excessive target grid."
    endif
    Make/D/N=(ne,nx,ny) EKxKy=NaN
    SetScale/P x e0,de,"eV",EKxKy
    SetScale/I y xmin,xmax,"pi/a",EKxKy
    SetScale/I z ymin,ymax,"pi/a",EKxKy
    EKxKy=MM_Pixel(x,y,z,source,Theta,Names,hv,workf,lc,toff,poff,phi0,rotation,center)
    Make/B/U/N=(ne,nx,ny) Coverage
    CopyScales EKxKy,Coverage
    Coverage=(numtype(EKxKy[p][q][r])==0)
    Make/D/N=(nx,ny) FermiSurface=NaN,ZeroEnergySlice=NaN
    SetScale/I x xmin,xmax,"pi/a",FermiSurface,ZeroEnergySlice
    SetScale/I y ymin,ymax,"pi/a",FermiSurface,ZeroEnergySlice
    for(ix=0;ix<nx;ix+=1)
        for(iy=0;iy<ny;iy+=1)
            total=0; valid=1
            for(ee=0;ee<ne-1;ee+=1)
                a=max(low,e0+ee*de); b=min(high,e0+(ee+1)*de)
                if(b<=a)
                    continue
                endif
                va=EKxKy[ee][ix][iy]; vb=EKxKy[ee+1][ix][iy]
                if(numtype(va+vb)!=0)
                    valid=0
                    break
                endif
                total+=(b-a)*(va+(a-e0-ee*de)/de*(vb-va)+va+(b-e0-ee*de)/de*(vb-va))/2
            endfor
            if(valid)
                FermiSurface[ix][iy]=total
            endif
            ZeroEnergySlice[ix][iy]=interp3D(EKxKy,0,xmin+ix*(xmax-xmin)/(nx-1),ymin+iy*(ymax-ymin)/(ny-1))
        endfor
    endfor
    // Round-trip every 20th detector point at first/middle/last energy.
    for(i=0;i<n;i+=1)
        Wave check=$(source+"PROCESS:"+Names[i])
        for(ee=0;ee<ne;ee+=max(1,floor((ne-1)/2)))
            ev=e0+de*ee
            k0=0.5118*lc/3.1416*sqrt(hv-workf+ev)
            for(j=1;j<nd-1;j+=20)
                beta=(center-d0-dd*j+phi0-poff)*pi/180
                t=(Theta[i]-toff)*pi/180
                kx=k0*sin(beta); ky=k0*sin(t)*cos(beta)
                xv=kx*cos(rotation*pi/180)-ky*sin(rotation*pi/180)
                yv=kx*sin(rotation*pi/180)+ky*cos(rotation*pi/180)
                actual=MM_Pixel(ev,xv,yv,source,Theta,Names,hv,workf,lc,toff,poff,phi0,rotation,center)
                if(numtype(actual)!=0)
                    Abort "Forward/inverse geometry round-trip returned non-finite intensity."
                endif
                residual=max(residual,abs(actual-check[ee][j]))
            endfor
        endfor
        WaveStats/Q check
        if(abs(V_sum-SourceSums[i])>1e-6)
            Abort "Source intensity changed during conversion."
        endif
    endfor
    Variable/G RoundtripMaxAbs=residual
    Variable/G PhotonEnergy=hv,WorkFunction=workf,LatticeConstant=lc
    Variable/G IntegrationLow=low,IntegrationHigh=high
    String/G Geometry="legacy GetEKxKyIntenTable; zero bias; phi common; RotationAngle; k units pi/a"
    String/G Status="memory_complete; technical trial; physical calibration unverified"
    Note EKxKy,"Axes: E relative to EF [eV], kx [pi/a], ky [pi/a]. Linear interpolation of measured processed CUTs. NaN outside coverage. No kz."
    Display/W=(80,80,660,490) as "Mechanical mapping - FS technical trial"
    AppendImage FermiSurface
    ModifyImage FermiSurface ctab={*,*,Terrain,0}
    Label bottom "kx (pi/a)"; Label left "ky (pi/a)"
    Display/W=(700,80,1280,490) as "I(E=0,kx,ky) - technical trial"
    AppendImage ZeroEnergySlice
    ModifyImage ZeroEnergySlice ctab={*,*,Terrain,0}
    Label bottom "kx (pi/a)"; Label left "ky (pi/a)"
    WaveStats/Q EKxKy
    Print "MM_MEMORY_COMPLETE",destination,"shape",ne,nx,ny,"finite",V_npnts,"NaN",V_numNaNs,"roundtrip_max_abs",residual
    SetDataFolder saved
End
