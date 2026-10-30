"""Deterministic offline motion compositor for FF short-form videos.

Requires Pillow and ffmpeg. Generated image/video assets and speech audio are
supplied by the chat agent; this script handles typography and MP4 rendering.
"""
import argparse
import json
import math
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


@lru_cache(maxsize=24)
def font(size):
    return ImageFont.truetype('DejaVuSans-Bold.ttf', size)


def load_project(path):
    project = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(project.get('scenes'), list) or not project['scenes']:
        raise ValueError('scenes must be a non-empty list')
    for field, default in (('width', 720), ('height', 1280), ('fps', 24)):
        project.setdefault(field, default)
    if not (240 <= project['width'] <= 1920 and 400 <= project['height'] <= 3840):
        raise ValueError('invalid video dimensions')
    if not (8 <= project['fps'] <= 60):
        raise ValueError('invalid fps')
    if not 1 <= len(project['scenes']) <= 30:
        raise ValueError('invalid scene count')
    for scene in project['scenes']:
        if not 0.3 <= scene.get('duration', 0) <= 30:
            raise ValueError('each scene requires duration between 0.3 and 30 seconds')
        if scene.get('type', 'title') not in {'title', 'image', 'compare', 'sequence', 'end'}:
            raise ValueError(f"invalid scene type: {scene.get('type')}")
    if sum(s['duration'] for s in project['scenes']) > 180:
        raise ValueError('video duration must not exceed 180 seconds')
    return project


def smooth(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)


def palette(project):
    return project.get('palette', {'bg': '#0B1931', 'fg': '#FFFFFF', 'accent': '#F6E83B', 'muted': '#9EC1EF'})


def center_text(draw, text, y, width, max_size, color, max_width=0.86):
    if not text:
        return y
    available = int(width * max_width)
    tokens = text.upper().split()
    lines, line = [], ''
    size = max_size
    face = font(size)
    for token in tokens:
        candidate = (line + ' ' + token).strip()
        if line and draw.textlength(candidate, font=face) > available:
            lines.append(line)
            line = token
        else:
            line = candidate
    if line:
        lines.append(line)
    while size > 15 and (max(draw.textlength(t, font=face) for t in lines) > available or len(lines) > 3):
        size -= 2
        face = font(size)
        lines, line = [], ''
        for token in tokens:
            candidate = (line + ' ' + token).strip()
            if line and draw.textlength(candidate, font=face) > available:
                lines.append(line)
                line = token
            else:
                line = candidate
        if line:
            lines.append(line)
    height = int(size * 1.18)
    for text_line in lines:
        text_width = draw.textlength(text_line, font=face)
        draw.text(((width - text_width) / 2, y), text_line, font=face, fill=color, stroke_width=0)
        y += height
    return y



def draw_text_box(draw, text, box, max_size, color, *, align="center", min_size=18):
    """Fit text within an explicit bounding box, or fail rather than clip.

    Returns the painted bounding rectangle for automated regression tests.
    The caller owns the box; never hide overflow with a later overlay.
    """
    x0, y0, x1, y1 = map(int, box)
    if x0 >= x1 or y0 >= y1 or not text:
        raise ValueError("invalid text box/text")
    tokens = text.upper().split()
    for size in range(max_size, min_size - 1, -1):
        face = font(size)
        lines = []
        line = ""
        for token in tokens:
            test = (line + " " + token).strip()
            if line and draw.textlength(test, font=face) > x1-x0:
                lines.append(line)
                line = token
            else:
                line = test
        if line:
            lines.append(line)
        if any(draw.textlength(part, font=face) > x1-x0 for part in lines):
            continue
        heights = []
        for part in lines:
            b = draw.textbbox((0, 0), part, font=face)
            heights.append(b[3]-b[1])
        step = max(1, round(size*1.2))
        height = (len(lines)-1)*step+max(heights)
        if height > y1-y0:
            continue
        y = y0 + (y1-y0-height)//2
        painted = []
        for part, ph in zip(lines, heights):
            tw = draw.textlength(part, font=face)
            x = x0 if align == "left" else round((x0+x1-tw)/2)
            b = draw.textbbox((x, y), part, font=face)
            draw.text((x, y), part, font=face, fill=color)
            painted.append(b)
            y += step
        actual = (min(b[0] for b in painted), min(b[1] for b in painted),
                  max(b[2] for b in painted), max(b[3] for b in painted))
        if actual[0] < x0 or actual[1] < y0 or actual[2] > x1 or actual[3] > y1:
            # Do not ever deliver a text render that violates its allocation.
            raise ValueError(f"text escaped its safe box: {actual} / {box}")
        return actual
    raise ValueError(f"Cannot fit text into safe box {box}: {text!r}")


def cube(draw, x, y, side, color, width=4):
    # Flat isometric wireframe cube; all geometry is deterministic.
    p = [(x, y), (x+side, y), (x+side, y+side), (x, y+side)]
    delta = int(side * 0.35)
    q = [(a+delta, b-delta) for a, b in p]
    draw.line(p + [p[0]], fill=color, width=width, joint='curve')
    draw.line(q + [q[0]], fill=color, width=width, joint='curve')
    for a,b in zip(p,q):
        draw.line([a,b], fill=color, width=width)


def make_frame(project, scene, local_time, global_time, asset=None):
    w, h = project['width'], project['height']
    colors = palette(project)
    bg, fg, accent, muted = (colors[x] for x in ('bg','fg','accent','muted'))
    canvas = Image.new('RGB', (w,h), bg)
    d = ImageDraw.Draw(canvas)
    progress = local_time / max(0.1, scene['duration'])
    s = w/720
    # Reusable subtle motion motifs; keep important copy clear.
    if asset is not None:
        shift = int(0.05 * w * math.sin(global_time * .42))
        canvas.paste(asset.crop((max(0, int(w*.06)+shift), int(h*.04), max(0,int(w*.06)+shift)+w, int(h*.04)+h)), (0,0))
        d = ImageDraw.Draw(canvas)
    else:
        for i in range(5):
            x = int((i*211*s + 55*s + 20*s*math.sin(global_time*.5+i)) % w)
            y = int((i*263*s + 95*s + 21*s*math.cos(global_time*.6+i)) % h)
            cube(d,x,y,int((28+(i%3)*13)*s),muted,width=max(1,int(2*s)))
        d.rounded_rectangle((int(56*s),int(320*s),int(664*s),int(1030*s)), radius=int(54*s),outline='#1D416C',width=max(1,int(2*s)))
    # Thin progress bar = repeatable channel signature.
    line_y = int(68*s)
    d.rounded_rectangle((int(56*s),line_y,int(664*s),line_y+max(2,int(5*s))), radius=4,fill='#37516D')
    d.rounded_rectangle((int(56*s),line_y,int(56*s)+int(608*s*smooth(progress)),line_y+max(2,int(5*s))), radius=4,fill=accent)
    if scene.get('overlay_text', True):
        # All editorial copy uses reserved safe zones, not guessed y offsets.
        label = scene.get('eyebrow', 'БЕСПОЛЕЗНЫЕ ФАКТЫ')
        draw_text_box(d, label, (int(56*s), int(100*s), int(664*s),
                                 int(160*s)), max(14, int(21*s)), accent,
                      align="left", min_size=max(10, int(13*s)))
        rise = int((1-smooth(local_time*4))*28*s)
        title = scene.get('title', '')
        if title:
            draw_text_box(d, title,
                          (int(56*s), int(205*s)+rise, int(664*s), int(460*s)),
                          max(22, int(64*s)), fg,
                          min_size=max(15, int(23*s)))
        caption = scene.get('caption', '')
        if caption:
            draw_text_box(d, caption,
                          (int(56*s), int(475*s), int(664*s), int(680*s)),
                          max(18, int(31*s)), muted,
                          min_size=max(13, int(18*s)))
    typ = scene.get('type','title')
    if typ == 'compare':
        cy, radius = int(785*s), int(75*s)
        lx,rx = int(228*s),int(492*s)
        # A cube that stays in place versus a sphere that rolls away.
        cube(d,lx-radius,cy-radius//2,int(100*s),accent,width=max(2,int(5*s)))
        roll = int(smooth(progress)*56*s)
        d.ellipse((rx-radius+roll,cy-radius,rx+radius+roll,cy+radius), fill='#5D8CFA',outline=fg,width=max(2,int(3*s)))
        draw_text_box(d, scene.get('left', 'КУБ'),
                      (int(56*s), int(935*s), int(330*s), int(1006*s)),
                      max(15, int(27*s)), fg, min_size=max(10, int(14*s)))
        draw_text_box(d, scene.get('right', 'ШАР'),
                      (int(390*s), int(935*s), int(664*s), int(1006*s)),
                      max(15, int(27*s)), fg, min_size=max(10, int(14*s)))
    elif typ == 'sequence':
        labels=scene.get('steps',['ФАКТ','ПОЧЕМУ','ВЫВОД'])[:4]
        n=len(labels)
        for i,label in enumerate(labels):
            x=int(w*(i+1)/(n+1))
            radius=int(45*s)
            d.rounded_rectangle((x-radius,int(765*s)-radius,x+radius,int(765*s)+radius),radius=int(15*s),fill=accent if i <= int(progress*n) else '#315C81')
            half = int(w / (n+1) * .46)
            draw_text_box(d, label, (x-half, int(847*s), x+half, int(920*s)),
                          max(12, int(18*s)), fg, min_size=max(9, int(11*s)))
            if i<n-1:
                d.line((x+radius+5,int(765*s),int(w*(i+2)/(n+1))-radius-5,int(765*s)),fill=fg,width=max(2,int(4*s)))
    elif typ in {'title','end'} and asset is None:
        big = int((115+10*math.sin(global_time*2))*s)
        cube(d,int(w/2-big/2),int(820*s-big/2),big,accent,width=max(3,int(6*s)))
    return canvas


def render_video(project, asset_dir, output, audio=None):
    if shutil.which('ffmpeg') is None:
        raise RuntimeError('ffmpeg is required')
    w,h,fps=project['width'],project['height'],project['fps']
    asset_dir=Path(asset_dir)
    images={}
    for index,scene in enumerate(project['scenes']):
        if scene.get('image'):
            path=asset_dir / scene['image']
            if not path.is_file():
                raise FileNotFoundError(f'image asset not found: {path}')
            with Image.open(path) as im:
                images[index]=ImageOps.fit(im.convert('RGB'),(int(w*1.2),int(h*1.08)),method=Image.Resampling.LANCZOS)
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    duration=sum(round(scene['duration']*fps)/fps for scene in project['scenes'])
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0']
    if audio:
        if not Path(audio).is_file():
            raise FileNotFoundError(f'audio not found: {audio}')
        cmd += ['-i',str(audio)]
    else:
        cmd += ['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=44100']
    cmd += ['-map','0:v:0','-map','1:a:0','-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    elapsed=0
    try:
        for index,scene in enumerate(project['scenes']):
            count=round(scene['duration']*fps)
            for j in range(count):
                frame=make_frame(project,scene,j/fps,elapsed+j/fps,images.get(index))
                proc.stdin.write(frame.tobytes())
            elapsed += count/fps
        proc.stdin.close()
        stderr=proc.stderr.read().decode('utf-8',errors='replace')
        if proc.wait()!=0:
            raise RuntimeError(f'ffmpeg failed: {stderr[-2000:]}')
        proc.stderr.close()
    except BaseException:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        proc.wait()
        proc.stderr.close()
        output.unlink(missing_ok=True)
        raise
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path)
    parser.add_argument('--assets',type=Path,default=Path('.'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audio',type=Path,help='Optional licensed music, SFX mix, or final narration track')
    args=parser.parse_args()
    p=load_project(args.project)
    print(render_video(p,args.assets,args.output,args.audio))


if __name__=='__main__':
    main()