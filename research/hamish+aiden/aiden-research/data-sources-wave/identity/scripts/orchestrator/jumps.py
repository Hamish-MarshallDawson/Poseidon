import csv,io,sys,zipfile,math,collections
Z=zipfile.ZipFile(sys.argv[1]);f=io.TextIOWrapper(Z.open(Z.namelist()[0]),encoding='utf-8',errors='replace')
r=csv.reader(f);next(r);last={};jump=collections.defaultdict(list);seen=set();bad=0
def hav(a,b,c,d):
    a,b,c,d=map(math.radians,(a,b,c,d));h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2;return 6371*2*math.asin(math.sqrt(h))
n=0
for x in r:
    try:
        cls=x[1];m=x[2];la=float(x[3]);lo=float(x[4]);t=x[0]
    except: continue
    if cls not in('Class A','Class B') or len(m)!=9 or m[:1] in('0','8','9'): continue
    if abs(la)>85 or (la==0 and lo==0) or not(45<la<70 and -15<lo<35): bad+=1;continue
    seen.add(m);sec=int(t[11:13])*3600+int(t[14:16])*60+int(t[17:19])
    if m in last:
        l,o,s=last[m];d=hav(l,o,la,lo);dt=sec-s
        if dt>0 and d>5 and d/dt*1943.8>60: jump[m].append(d)
    last[m]=(la,lo,sec);n+=1
print('rows',n,'mobile MMSI',len(seen),'dropped rows outside range or sentinel',bad)
big=[(m,len(v),round(max(v))) for m,v in jump.items()]
print('MMSIs with any >60 kn and >5 km jump',len(big),f'{100*len(big)/len(seen):.2f}%','repeated ≥3 jumps',sum(b[1]>=3 for b in big),'max jump km',max(b[2] for b in big) if big else None)
print('over 100 km',sum(b[2]>100 for b in big),'over 1000 km',sum(b[2]>1000 for b in big));print(sorted(big,key=lambda b:-b[1])[:10])
print({m:(len(jump[m]),round(max(jump[m]))) for m in('219018851','246843000') if m in jump})
