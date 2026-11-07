import gzip, h3
rows={}
with open('/tmp/gj.csv','rb') as f:
    txt=gzip.decompress(f.read()).decode()
for i,line in enumerate(txt.splitlines()):
    if i==0: continue
    h,g,b=line.split(','); rows[h]=(int(g),int(b))
pts={'Gulf of Finland':(59.6,24.5),'Danish straits':(55.5,12.5),'Gotland basin':(58.0,19.0),
     'Hormuz':(26.6,56.4),'Gulf of Oman':(24.8,58.0),'Natuna':(3.0,107.5),'Malacca':(2.6,101.2),
     'Red Sea (Bab el-Mandeb)':(13.0,43.0),'Black Sea west':(43.5,30.5),'Eastern Med':(34.0,32.0)}
print(f"{'region':26} {'cells':>5} {'good':>8} {'bad':>6} {'pct_bad':>8} {'red_cells':>9} {'worst_pct':>9}")
for name,(la,lo) in pts.items():
    c=h3.latlng_to_cell(la,lo,4)
    cells=h3.grid_disk(c,4)
    g=b=0; red=0; worst=0
    for cid in cells:
        if cid in rows:
            gg,bb=rows[cid]; g+=gg; b+=bb
            p=100*bb/(gg+bb) if gg+bb else 0
            worst=max(worst,p)
            if p>10: red+=1
    print(f"{name:26} {len(cells):5} {g:8} {b:6} {100*b/(g+b) if g+b else 0:8.2f} {red:9} {worst:9.1f}")
tot_g=sum(v[0] for v in rows.values()); tot_b=sum(v[1] for v in rows.values())
print('world total good/bad', tot_g, tot_b, f'{100*tot_b/(tot_g+tot_b):.2f}%')
