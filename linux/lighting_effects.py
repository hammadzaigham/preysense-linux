"""PreySense four-zone software lighting effects."""
import colorsys,math,random
SOFTWARE_EFFECTS = (
    'Rainbow Cycle', 'Police Strobe', 'Fire Ember', 'Matrix Cascade',
    'Cylon Scanner', 'Aurora Drift', 'Heartbeat', 'Lightning Storm', 'Starlight',
    'Neon Pulse', 'Plasma Orb', 'Glitch Storm', 'Bio Hazard', 'Solar Flare',
    'Ocean Tide', 'Ice Crystal',
)

def scale(color,factor):return tuple(round(v*max(0,min(1,factor))) for v in color)
def lerp(a,b,t):return tuple(round(x+(y-x)*max(0,min(1,t))) for x,y in zip(a,b))
def frame(effect,step,count,brush=(0,240,255),speed=50,rng=None):
    rng=rng or random
    if effect not in SOFTWARE_EFFECTS:raise ValueError('Unknown software lighting effect')
    if effect=='Rainbow Cycle':return [tuple(round(v*255) for v in colorsys.hsv_to_rgb(((step*48+i*90)%360)/360,1,1)) for i in range(4)]
    if effect=='Police Strobe':return [(0,85,255)]*2+[(5,5,10)]*2 if (count//4)%2==0 else [(5,5,10)]*2+[(255,0,34)]*2
    if effect=='Fire Ember':
        values=[.85+math.sin(step*1.8)*.15+math.sin(step*3.7)*.1,.95+math.sin(step*1.8+1.2)*.18+math.sin(step*4.1+.5)*.12,.9+math.sin(step*1.8+2.4)*.16+math.sin(step*3.3+1.1)*.11,.8+math.sin(step*1.8+3.6)*.19+math.sin(step*4.5+2)*.13]
        return [tuple(int(min(255,v)) for v in (255*max(0,min(1.2,x)),(55+max(0,min(1.2,x))*120)*.75,max(0,min(1.2,x))*18)) for x in values]
    if effect=='Matrix Cascade':
        head=(count//3)%6
        return [(57,255,20) if i==head else (0,150,25) if i==head-1 else (0,55,12) if i==head-2 else (0,16,4) for i in range(4)]
    if effect=='Cylon Scanner':return [brush if i==[0,1,2,3,2,1][(count//3)%6] else (12,0,6) for i in range(4)]
    if effect=='Aurora Drift':return [lerp((0,245,212),(123,44,191),(math.sin(step*.45+i*.85)+1)/2) for i in range(4)]
    if effect=='Ocean Tide':return [lerp((0,32,96),(0,220,255),(math.sin(step*.95+i*.85)+1)/2) for i in range(4)]
    if effect=='Heartbeat':
        t=(step*.42)%1
        pulse=t/.1 if t<.1 else 1-(t-.1)/.1 if t<.2 else (t-.2)/.1*.62 if t<.3 else .62-(t-.3)/.1*.62 if t<.4 else .08
        return [scale(brush,max(.08,min(1,pulse)))]*4
    if effect=='Lightning Storm':
        result=[(8,10,28)]*4
        if count%max(5,22-speed//6)==0 or rng.random()<.06:
            zone=rng.randrange(4);bolt=(235,245,255) if rng.random()<.45 else (110,170,255);result[zone]=bolt
            if zone>0:result[zone-1]=scale(bolt,.32)
            if zone<3:result[zone+1]=scale(bolt,.32)
        return result
    if effect=='Starlight':return [lerp((6,8,20),(210,225,255),((math.sin(step*1.35+i*1.73)+1)/2)**5) for i in range(4)]
    if effect == 'Neon Pulse':
        cycle = (step * .28) % 1
        pulse = max(.04, cycle / .08 if cycle < .08 else math.exp(-(cycle - .08) / .92 * 3.5))
        color = lerp(brush, (255, 255, 255), max(0, (pulse - .88) / .12) * .65)
        return [scale(color, pulse)] * 4
    if effect == 'Plasma Orb':
        colors = []
        for zone in range(4):
            phase = zone * math.pi / 2
            hue = (step * 22 + math.sin(step * .6 + phase) * 110) % 360
            saturation = .8 + math.sin(step * 1.1 + phase) * .2
            colors.append(tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue / 360, saturation, 1)))
        return colors
    if effect == 'Glitch Storm':
        colors = [(4, 4, 8)] * 4
        forced = count % max(8, 35 - int(speed * .27)) == 0
        if forced or rng.random() <= .04 + speed * .0022:
            for _ in range(rng.randrange(2, 4) if forced else rng.randrange(1, 3)):
                zone, hue = rng.randrange(4), rng.random()
                colors[zone] = (240, 240, 255) if rng.random() < .18 else tuple(
                    round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, 1, 1))
        return colors
    if effect == 'Bio Hazard':
        colors = []
        position = (step * .55) % 6
        for zone in range(4):
            distance = abs(min(position, 6 - position) - zone)
            glow = 1 - distance * 1.5 if distance < .5 else max(0, .55 - (distance - .5) * .55)
            colors.append(lerp((60, 180, 0), (180, 255, 0), (glow - .6) / .4) if glow > .6
                          else lerp((5, 28, 2), (60, 180, 0), glow / .6))
        return colors
    if effect == 'Solar Flare':
        colors = [(100, 20, 0), (130, 35, 0), (110, 25, 0), (90, 18, 0)]
        periodic = count % max(6, 28 - int(speed * .22)) == 0
        if periodic or rng.random() <= .05 + speed * .0018:
            zone, roll = rng.randrange(4), rng.random()
            flare = (255, 255, 220) if roll < .35 else (255, 230, 80) if roll < .65 else (255, 160, 20)
            colors[zone] = flare
            for neighbor in (zone - 1, zone + 1):
                if 0 <= neighbor < len(colors):
                    colors[neighbor] = lerp(colors[neighbor], flare, .45)
        return colors
    return [lerp((36,82,150),(190,235,255),max(0,min(1,(math.sin(step*1.05+i*1.25)+1)/2*.72+((math.sin(step*3.2+i*2.05)+1)/2)**3*.28))) for i in range(4)]
