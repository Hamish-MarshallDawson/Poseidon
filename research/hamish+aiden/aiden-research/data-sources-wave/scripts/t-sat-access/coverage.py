import datetime as dt, json, math, statistics as st, time
from pystac_client import Client
from shapely.geometry import shape, Point

NOW = dt.datetime(2026,11,7,16,30,tzinfo=dt.timezone.utc)
SUN = dt.datetime(2026,11,8,12,0,tzinfo=dt.timezone.utc)
START = NOW - dt.timedelta(days=30)
POINTS = {
 'Gulf of Finland':(24.70,59.90), 'Danish straits':(12.60,55.40), 'English Channel':(1.50,50.80),
 'Hormuz':(56.40,26.60), 'Gulf of Oman':(57.50,24.80), 'Red Sea':(39.00,18.00),
 'Malacca':(100.00,3.50), 'Natuna':(107.00,3.50), 'South China Sea open':(114.00,12.00),
 'Gulf of Guinea':(3.00,3.50), 'mid-Atlantic':(-30.00,40.00)}
d=0.06
c = Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=120)
out={}
for name,(lon,lat) in POINTS.items():
    bbox=[lon-d,lat-d,lon+d,lat+d]
    t0=time.time()
    try:
        items=[i for i in c.search(collections=['sentinel-1-grd'], bbox=bbox,
               datetime=f"{START:%Y-%m-%dT%H:%M:%SZ}/{NOW:%Y-%m-%dT%H:%M:%SZ}", limit=1000).items()]
    except Exception as e:
        out[name]={'error':repr(e)[:200]}; print(name,'ERR',e); continue
    pt=Point(lon,lat); rows=[]
    for it in items:
        try: geom=shape(it.geometry)
        except Exception: continue
        if not geom.contains(pt): continue
        sense=it.datetime
        proc=it.properties.get('s1:processing_datetime')
        proc=dt.datetime.fromisoformat(proc.replace('Z','+00:00')) if proc else None
        rows.append({'id':it.id,'sense':sense,'proc':proc,'platform':it.properties.get('platform'),
                     'rel_orbit':it.properties.get('sat:relative_orbit'),'orbit':it.properties.get('sat:orbit_state'),
                     'slice':it.properties.get('s1:slice_number'),'tlm':it.properties.get('s1:product_timeliness'),
                     'transform':it.properties.get('proj:transform'),'shape':it.properties.get('proj:shape')})
    rows.sort(key=lambda r:r['sense'])
    n=len(rows)
    delays=[(r['proc']-r['sense']).total_seconds()/3600 for r in rows if r['proc']]
    gaps=[(rows[i+1]['sense']-rows[i]['sense']).total_seconds()/3600 for i in range(n-1)]
    # forecast: same platform+rel_orbit, 12-day shift
    fc=[]
    for r in rows:
        for shift in (12,):
            t=r['sense']+dt.timedelta(days=shift)
            if NOW<=t<=SUN: fc.append((t.isoformat(), r['platform'], r['rel_orbit'], r['orbit']))
    out[name]={'n':n,'n_all_box_items':len(items),'querys':round(time.time()-t0,2),
      'per_week':round(n/30*7,2),
      'delay_med_h':round(st.median(delays),2) if delays else None,
      'delay_max_h':round(max(delays),2) if delays else None,
      'delay_n':len(delays),
      'gap_max_h':round(max(gaps),1) if gaps else None,
      'gap_med_h':round(st.median(gaps),1) if gaps else None,
      'last_pass':rows[-1]['sense'].isoformat() if n else None,
      'platforms':sorted({r['platform'] for r in rows}),
      'orbs':sorted({(r['platform'],r['rel_orbit'],r['orbit']) for r in rows}),
      'tlm':sorted({r['tlm'] for r in rows}),
      'sample_transform':rows[-1]['transform'] if n else None,
      'sample_shape':rows[-1]['shape'] if n else None,
      'series':[(r['sense'].isoformat(),r['platform'],r['rel_orbit'],r['orbit']) for r in rows],
      'forecast':fc}
    print(f"{name:22s} n={n:3d} /wk={out[name]['per_week']:4.2f} delay_med={out[name]['delay_med_h']} maxgap={out[name]['gap_max_h']} last={out[name]['last_pass']}")
json.dump(out, open('/tmp/tsat/coverage.json','w'), indent=1)
print('\nFORECAST now->Sun 12:00 UTC (12-day shift of observed passes):')
for k,v in out.items():
    if v.get('forecast'): print(' ',k,v['forecast'])
