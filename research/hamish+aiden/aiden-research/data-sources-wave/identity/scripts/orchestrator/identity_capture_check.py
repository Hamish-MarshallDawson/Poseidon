import json,sys,collections,re
ok=lambda i:len(i)==7 and i.isdigit() and sum(int(i[j])*(7-j) for j in range(6))%10==int(i[6])
JUNK={'0','1','1234567','100000000','999999999'}
N=lambda s:re.sub(r'[^A-Z0-9]','',(s or '').upper())
m2i=collections.defaultdict(set);i2m=collections.defaultdict(set);m2n=collections.defaultdict(set);m2raw=collections.defaultdict(set);st=0;zero=0;bad=0;t=[];n=0;seen=set()
for l in open(sys.argv[1]):
    try:r=json.loads(l)
    except:continue
    n+=1;t.append(r['recv']);d=r['msg'];seen.add((d.get('MetaData') or {}).get('MMSI'))
    if d.get('MessageType')!='ShipStaticData':continue
    s=d['Message']['ShipStaticData'];st+=1;m=str(s.get('UserID'));i=str(s.get('ImoNumber') or 0)
    if i=='0':zero+=1
    elif not ok(i) or i in JUNK:bad+=1
    else:m2i[m].add(i);i2m[i].add(m)
    if s.get('Name','').strip():m2n[m].add(N(s['Name']));m2raw[m].add(s['Name'].strip())
print('messages',n,'minutes',round((t[-1]-t[0])/60,1),'MMSIs',len(seen),'static',st,'IMO zero',f'{100*zero/st:.0f}%','invalid or placeholder',f'{100*bad/st:.1f}%')
print('static MMSIs valid IMO',len(m2i),'with 2 IMOs',sum(len(v)>1 for v in m2i.values()),'valid IMOs',len(i2m),'on 2+ MMSIs',sum(len(v)>1 for v in i2m.values()),[(k,sorted(v)) for k,v in i2m.items() if len(v)>1][:6])
print('MMSIs with name',len(m2n),'raw names 2+',sum(len(v)>1 for v in m2raw.values()),'normalised names 2+',sum(len(v)>1 for v in m2n.values()),[sorted(v) for v in m2n.values() if len(v)>1][:5])
