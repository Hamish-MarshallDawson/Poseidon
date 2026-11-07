BEGIN{FS=","}
NR>1{
  mmsi=$3; lat=$4+0; lon=$5+0;
  # drop sentinel / bad fixes
  if (lat>90 || lat<-90 || lon>180 || lon<-180 || (lat==0 && lon==0) || (lat==91) || (lon==0 && lat>89)) next;
  split($1,a," "); split(a[1],d,"/"); split(a[2],t,":");
  ts=d[3]*86400+d[2]*3600+t[1]*60+t[2]+t[3]/60;
  if (mmsi in plat) {
    la=plat[mmsi]; lo=plon[mmsi]; pt=pts[mmsi];
    dt=ts-pt; if (dt<0.0001) dt=0.0001;
    # haversine in metres
    pi=3.14159265358979; r=6371000;
    p1=la*pi/180; p2=lat*pi/180; dp=(lat-la)*pi/180; dl=(lon-lo)*pi/180;
    h=sin(dp/2)^2+cos(p1)*cos(p2)*sin(dl/2)^2;
    dist=2*r*atan2(sqrt(h),sqrt(1-h));
    kn=dist/dt*1.94384;
    fixes[mmsi]++;
    if (dist>3000 && kn>100) { cnt[mmsi]++; if(!(mmsi in ex)) {ex[mmsi]=sprintf("dist=%.0fm dt=%.0fs kn=%.0f at %s",dist,dt,kn,$1)} }
    maxk[mmsi]=(kn>maxk[mmsi])?kn:maxk[mmsi];
  }
  plat[mmsi]=lat; plon[mmsi]=lon; pts[mmsi]=ts;
}
END{
  n=0; tot=0;
  for (m in cnt) { n++; tot+=cnt[m] }
  print "ship_mmsi_with_impossible_jump", n, "pairs", tot;
  c=0; for (m in ex) { if (c<12) { print m, ex[m]; c++ } }
}
