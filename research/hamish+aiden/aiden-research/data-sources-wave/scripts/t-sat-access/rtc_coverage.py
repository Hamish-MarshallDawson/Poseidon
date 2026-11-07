import datetime as dt, json, statistics as st
from shapely.geometry import shape, Point
from pystac_client import Client
NOW=dt.datetime(2026,11,7,16,30,tzinfo=dt.timezone.utc); START=NOW-dt.timedelta(days=30)
PTS={'Gulf of Finland':(24.70,59.90),'Danish straits':(12.60,55.40),'English Channel':(1.50,50.80),
 'Hormuz':(56.40,26.60),'Gulf of Oman':(57.50,24.80),'Red Sea':(39.00,18.00),'Malacca':(100.00,3.50),
 'Natuna':(107.00,3.50),'South China Sea open':(114.00,12.00),'Gulf of Guinea':(3.00,3.50),'mid-Atlantic':(-30.00,40.00)}
c=Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=120)
out={}
for n,(lon,lat) in PTS.items():
    items=[i for i in c.search(collections=['sentinel-1-rtc'], bbox=[lon-.06,lat-.06,lon+.06,lat+.06],
           datetime=f"{START:%Y-%m-%dT%H:%M:%SZ}/{NOW:%Y-%m-%dT%H:%M:%SZ}", limit=500).items()]
    pt=Point(lon,lat)
    items=[i for i in items if i.datetime and shape(i.geometry).contains(pt)]
    items.sort(key=lambda i:i.datetime)
    dl=[]
    for i in items:
        p=i.properties.get('s1:processing_datetime') or i.properties.get('created')
        if p: dl.append((dt.datetime.fromisoformat(p.replace('Z','+00:00'))-i.datetime).total_seconds()/3600)
    gaps=[(items[k+1].datetime-items[k].datetime).total_seconds()/3600 for k in range(len(items)-1)]
    out[n]={'rtc_n':len(items),'per_week':round(len(items)/30*7,2),
            'deliv_med_h':round(st.median(dl),2) if dl else None,'deliv_max_h':round(max(dl),1) if dl else None,
            'gap_max_h':round(max(gaps),1) if gaps else None,'last':items[-1].datetime.isoformat() if items else None,
            'platforms':sorted({i.properties.get('platform') for i in items})}
    print(f"{n:22s} {out[n]}")
json.dump(out, open('/tmp/tsat/rtc_coverage.json','w'), indent=1)
