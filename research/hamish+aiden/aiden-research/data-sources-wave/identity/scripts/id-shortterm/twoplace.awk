BEGIN{FS=","}
NR>1{
  mmsi=$3; lat=$4+0; lon=$5+0;
  if (lat>90 || lat<-90 || lon>180 || lon<-180 || (lat==0 && lon==0) || lat==91) next;
  split($1,a," "); split(a[1],d,"/"); split(a[2],t,":");
  ts=d[3]*86400+d[2]*3600+t[1]*60+t[2]+t[3]/60;
  if (mmsi in plat) {
    la=plat[mmsi]; lo=plon[mmsi]; pt=pts[mmsi];
    dt=ts-pt; if (dt<0) dt=0;
    pi=3.14159265358979; r=6371000;
    p1=la*pi/180; p2=lat*pi/180; dp=(lat-la)*pi/180; dl=(lon-lo)*pi/180;
    h=sin(dp/2)^2+cos(p1)*cos(p2)*sin(dl/2)^2;
    dist=2*r*atan2(sqrt(h),sqrt(1-h));
    if (dist>5000 && dt<=2) { same[mmsi]++; if(!(mmsi in exs)) exs[mmsi]=sprintf("%.0fkm dt=%.0fs %s",dist/1000,dt,$1) }
    if (dist>20000 && dt>2 && dt<=120) { fast[mmsi]++; if(!(mmsi in exf)) exf[mmsi]=sprintf("%.0fkm dt=%.0fs kn=%.0f %s",dist/1000,dt,dist/dt*1.94384,$1) }
    if (dist>20000 && (mmsi in plast) && dt<=300) {
      la2=plast[mmsi]; lo2=plon2[mmsi];
      p3=la2*pi/180; dp2=(lat-la2)*pi/180; dl2=(lon-lo2)*pi/180;
      h2=sin(dp2/2)^2+cos(p2)*cos(p3)*sin(dl2/2)^2;
      back=2*r*atan2(sqrt(h2),sqrt(1-h2));
      if (back<3000) { ret[mmsi]++; if(!(mmsi in exr)) exr[mmsi]=sprintf("%.0fkm then back %.1fkm %s",dist/1000,back/1000,$1) }
    }
    plast[mmsi]=la; plon2[mmsi]=lo;
  }
  plat[mmsi]=lat; plon[mmsi]=lon; pts[mmsi]=ts;
}
END{
  ns=0;tsum=0; for(m in same){ns++;tsum+=same[m]}
  print "A_same_second_far_apart_mmsi",ns,"pairs",tsum;
  nf=0;tfast=0; for(m in fast){nf++;tfast+=fast[m]}
  print "B_fast_travel_lt120s_mmsi",nf,"pairs",tfast;
  nr=0;tret=0; for(m in ret){nr++;tret+=ret[m]}
  print "C_return_pattern_mmsi",nr,"pairs",tret;
  print "--- A examples"; c=0; for(m in exs){ if(c++<10) print m, exs[m] }
  print "--- B examples"; c=0; for(m in exf){ if(c++<10) print m, exf[m] }
  print "--- C examples"; c=0; for(m in exr){ if(c++<6) print m, exr[m] }
}
