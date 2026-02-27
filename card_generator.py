import os
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import math
import subprocess

# Usaremos fontes do sistema
FONT_PATH_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_PATH_REGULAR = "C:/Windows/Fonts/arial.ttf"

def generate_frames_for_clip(temp_dir, rank_info, theme_title, video_frames_dir=None, duration=5.0, fps=30):
    """
    Gera uma sequência de imagens PNG transparentes (frames) com o card animado.
    """
    frames_dir = Path(temp_dir) / f"frames_{rank_info['rank']}"
    frames_dir.mkdir(exist_ok=True)
    
    total_frames = int(duration * fps)
    
    # Textos
    rank = f"#{rank_info['rank']}"
    artist = rank_info['artist']
    song = rank_info['song']
    stat = rank_info['stat']
    
    # Tentar extrair número e sufixo do stat (ex: "2.5 Billion Views" -> 2.5, " Billion Views")
    match = re.search(r'([\d\.,]+)\s*(.*)', stat)
    target_num = 0.0
    suffix = stat
    if match:
        try:
            target_num = float(match.group(1).replace(',', ''))
            suffix = match.group(2)
        except:
            target_num = 0.0
            suffix = stat
            
    # Tamanho do vídeo (9:16)
    W, H = 1080, 1920
    
    # Cores
    neon_color = (0, 255, 128, 255) # Verde neon
    bg_color = (20, 20, 30, 200) # Dark glass
    text_color = (255, 255, 255, 255)
    
    # Fontes
    try:
        font_rank = ImageFont.truetype(FONT_PATH_BOLD, 140)
        font_song = ImageFont.truetype(FONT_PATH_BOLD, 60)
        font_artist = ImageFont.truetype(FONT_PATH_REGULAR, 45)
        font_stat = ImageFont.truetype(FONT_PATH_BOLD, 50)
        font_title = ImageFont.truetype(FONT_PATH_BOLD, 70)
    except IOError:
        font_rank = ImageFont.load_default()
        font_song = ImageFont.load_default()
        font_artist = ImageFont.load_default()
        font_stat = ImageFont.load_default()
        font_title = ImageFont.load_default()

    # Preparar máscara circular para os frames do vídeo
    thumb_size = 300
    mask = Image.new("L", (thumb_size, thumb_size), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, thumb_size, thumb_size), fill=255)
    
    last_valid_thumb = None
    
    for frame_idx in range(total_frames):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        t = frame_idx / fps
        
        # Carregar o frame do vídeo para o thumbnail
        thumb_img = None
        if video_frames_dir:
            # ffmpeg geralmente começa em 1, então frame_idx + 1
            frame_file = Path(video_frames_dir) / f"thumb_{frame_idx + 1:04d}.jpg"
            if frame_file.exists():
                try:
                    thumb_raw = Image.open(frame_file).convert("RGBA")
                    thumb_raw = thumb_raw.resize((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                    thumb_img = Image.new("RGBA", (thumb_size, thumb_size), (0,0,0,0))
                    thumb_img.paste(thumb_raw, (0,0), mask)
                    
                    # Adicionar borda neon
                    draw_thumb = ImageDraw.Draw(thumb_img)
                    draw_thumb.ellipse((0, 0, thumb_size-1, thumb_size-1), outline=neon_color, width=8)
                    last_valid_thumb = thumb_img
                except Exception as e:
                    thumb_img = last_valid_thumb
            else:
                thumb_img = last_valid_thumb
        
        # Animação de entrada (Slide de baixo para cima + Fade In)
        slide_duration = 0.8
        progress = min(t / slide_duration, 1.0)
        # Ease out cubic
        ease = 1 - pow(1 - progress, 3)
        
        y_offset = int((1 - ease) * 500)
        alpha_mult = int(ease * 255)
        
        # Desenhar Cabeçalho (Título do Tema)
        title_y = 150
        # draw shadow
        draw.text((W/2 + 5, title_y + 5), theme_title.upper(), font=font_title, fill=(0,0,0,alpha_mult), anchor="mm")
        draw.text((W/2, title_y), theme_title.upper(), font=font_title, fill=(255,255,255,alpha_mult), anchor="mm")
        
        # Parâmetros do Card Central
        card_w = 900
        card_h = 500
        card_x = (W - card_w) // 2
        card_y = (H - card_h) // 2 + y_offset
        
        # Desenhar Shadow do Card
        shadow_rect = [card_x - 10, card_y - 10, card_x + card_w + 10, card_y + card_h + 10]
        draw.rounded_rectangle(shadow_rect, radius=40, fill=(0, 0, 0, int(100 * ease)))
        
        # Desenhar Fundo do Card (Glass)
        card_rect = [card_x, card_y, card_x + card_w, card_y + card_h]
        draw.rounded_rectangle(card_rect, radius=30, fill=(20, 20, 30, int(220 * ease)), outline=neon_color, width=4)
        
        # Desenhar Rank
        draw.text((card_x + 50, card_y + 50), rank, font=font_rank, fill=neon_color[:3] + (alpha_mult,))
        
        # Desenhar Thumbnail (AGORA ANIMADO COM O CLIPE)
        if thumb_img:
            # Misturar alpha do thumb com o alpha da animação
            t_img = thumb_img.copy()
            if alpha_mult < 255:
                t_img.putalpha(t_img.split()[3].point(lambda p: p * (alpha_mult/255.0)))
            img.paste(t_img, (card_x + card_w - 350, card_y + 100), t_img)
            
        # Textos: Song e Artist
        text_start_x = card_x + 50
        song_y = card_y + 220
        artist_y = song_y + 70
        
        # Truncar nomes muito longos
        display_song = song if len(song) < 22 else song[:19] + "..."
        display_artist = artist if len(artist) < 25 else artist[:22] + "..."
        
        draw.text((text_start_x, song_y), display_song, font=font_song, fill=(255,255,255,alpha_mult))
        draw.text((text_start_x, artist_y), display_artist, font=font_artist, fill=(180,180,180,alpha_mult))
        
        # Animação do Contador (Odômetro)
        count_duration = 1.5
        count_progress = min(max(t - slide_duration + 0.2, 0) / count_duration, 1.0)
        # Ease out quad for counter
        c_ease = 1 - (1 - count_progress) * (1 - count_progress)
        
        current_num = target_num * c_ease
        
        if target_num > 0:
            if isinstance(target_num, float) and target_num < 100: # Ex: 2.5 Billion
                display_stat = f"{current_num:.1f} {suffix}"
            else: # Ex: 2500000
                display_stat = f"{int(current_num):,} {suffix}".replace(',', '.')
        else:
            display_stat = stat # Se falhou ao extrair, mostra estático
            
        stat_y = artist_y + 100
        draw.text((text_start_x, stat_y), display_stat, font=font_stat, fill=neon_color[:3] + (alpha_mult,))
        
        # Salvar Frame
        out_path = frames_dir / f"frame_{frame_idx:04d}.png"
        img.save(out_path)
        
    return str(frames_dir)
