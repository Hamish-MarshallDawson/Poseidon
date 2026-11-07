BEGIN{FS=","; split("246843000 245455000 636015105 211895580 246719000 240565000 231200000 273218630 212810000 219018851",a," "); for(i in a) want[a[i]]=1}
NR>1{
  m=$3; if(!(m in want)) next;
  lat=$4+0; lon=$5+0;
  if (lat>90||lat<-90||lon>180||lon<-180||(lat==0&&lon==0)||lat==91) next;
  g=int(lat*10)"/"int(lon*10); c[m"|"g]++; n[m]++; if(!(m in t0)) t0[m]=$1; t1[m]=$1;
}
END{
  for (m in n) {
    line=""; c2=0;
    for (k in c) { split(k,p,"|"); if(p[1]==m) { cells[m]=cells[m]" "p[2]"="c[k]; c2++ } }
    print m, "fixes="n[m], "cells="c2, t0[m]".."t1[m], cells[m];
  }
}
